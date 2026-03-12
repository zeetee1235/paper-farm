<img src="docs/logo.png" alt="paper-farm" width="160" align="left" style="margin-right:24px; margin-bottom:4px;" />

# paper-farm

로컬 환경에서 완결되는 체계적 문헌 관리 파이프라인. paper-farm은 Zotero 스토리지를 모니터링하여 새로운 연구 PDF를 감지하고, 다단계 텍스트 추출 및 정규화를 수행한 뒤 로컬에서 실행되는 LLM을 활용한 map-reduce 전략으로 구조화된 요약을 생성하여 Obsidian 볼트에 주석 포함 Markdown 노트로 저장합니다. 모든 처리는 외부 서비스로의 문서 전송 없이 로컬에서 완료됩니다.

English: [README.md](./README.md)

<br clear="left" />

---

## 아키텍처

<p align="center">
  <img src="docs/pipeline.svg" alt="paper-farm pipeline" width="870"/>
</p>

> **Fig. 1.** 전체 처리 파이프라인. 큐 기반 워처 스레드가 설정된 주기로 Zotero 스토리지를 폴링하고, 감지된 PDF를 큐에 추가하여 텍스트 추출 → 정규화 → LLM 요약 → Obsidian 내보내기 4단계를 순차적으로 처리합니다. 각 단계의 결과는 다음 단계 시작 전 디스크에 저장됩니다.

### 파이프라인 단계

| 단계 | 모듈 | 설명 |
|------|------|------|
| **Ingest** | `watchers/` | Zotero 스토리지 폴링, 경로 해시 기반 중복 제거, 신규 PDF 큐 추가 |
| **Extract & Normalize** | `extractors/`, `normalizers/` | 품질 게이팅을 포함한 2단계 텍스트 추출, 섹션 경계 감지 |
| **Summarize** | `summarizers/` | Map-reduce LLM 요약, 구조화된 JSON 출력 |
| **Export** | `exporters/` | YAML 프론트매터를 포함한 Markdown 렌더링, Obsidian 볼트 디렉터리 생성 |

각 논문은 Obsidian 볼트 내 독립적인 디렉터리를 생성합니다:

```
<obsidian-vault>/
  NNN_<paper-id>/
    summary.md      ← YAML 프론트매터 포함 구조화 요약 (LLM 생성)
    metadata.json   ← 제목, 저자, 연도, 학회, DOI, paper_num, 태그
    notes.md        ← 사용자 노트 템플릿 (연구 아이디어 / 질문 / 후속 논문)
    paper.pdf       ← 원본 PDF 사본
```

`NNN`은 첫 내보내기 시 할당되는 3자리 고정 식별자로, `metadata.json`에 영구 저장됩니다. 이후 파이프라인 재실행 시에도 동일한 번호가 유지됩니다.

---

## 요구사항

- Python 3.11+
- [Ollama](https://ollama.com) 로컬 실행 중 — `ollama serve`
- 모델 다운로드 완료, 예: `ollama pull phi4:14b`
- *(선택)* Rust 툴체인 — 스캔본 PDF에 OCR이 필요한 경우에만

---

## 설치

```bash
git clone --recurse-submodules <repo-url>
cd paper-farm-lab

# uv 사용 (권장)
uv sync

# 또는 pip
pip install -e .
```

---

## 설정

```bash
paper-farm init-config        # 현재 디렉터리에 paper-farm.toml 생성
```

생성된 파일을 편집합니다:

```toml
[paths]
obsidian_vault = "~/Documents/Obsidian/Research/papers"

[llm]
backend  = "ollama"
model    = "phi4:14b"         # ollama pull phi4:14b 실행 필요
timeout  = 600                # 초 단위; 14B 모델에는 600 권장

[summary]
language = "ko"               # en / ko / ja / zh / fr / de / es

[watcher]
zotero_storage = "~/Zotero/storage"
poll_interval  = 30           # 스캔 주기 (초)
```

> **Zotero 경로**
> macOS / Windows: `~/Zotero/storage` · Linux (snap): `~/snap/zotero-snap/common/Zotero/storage`

---

## 사용법

### 자동 모드 (권장)

Zotero를 감시하며 새 논문 자동 처리:

```bash
paper-farm watch
```

또는 헬퍼 스크립트 사용:

```bash
scripts/start-watch.sh       # 워처 실행 + logs/ 에 로그 저장
scripts/monitor.sh           # 실시간 대시보드 (큐 현황, 진행 상태, 최근 로그)
```

### 수동 모드

```bash
# 전체 파이프라인 한 번에
paper-farm run /path/to/paper.pdf --title "논문 제목" \
    --authors "홍길동, 김철수" --year 2024

# 단계별 실행
paper-farm ingest    /path/to/paper.pdf
paper-farm parse     <paper-id>
paper-farm summarize <paper-id>
paper-farm export    <paper-id>
```

### 목록 / 상태 확인

```bash
paper-farm list               # 등록된 논문 전체 목록
paper-farm show <paper-id>    # 각 단계별 아티팩트 상태 확인
```

---

## 텍스트 추출

<p align="center">
  <img src="docs/extraction.svg" alt="Smart extraction flow" width="500"/>
</p>

> **Fig. 2.** 2단계 추출 전략. pypdf를 먼저 시도하고, 5개 신호로 구성된 품질 점수가 임계값(60/100점) 미만이면 DocStruct OCR(Rust/Tesseract 기반)로 전환합니다.

텍스트 추출은 자동 품질 게이팅을 포함한 2단계 전략을 사용합니다:

1. **1차 시도 (pypdf):** 텍스트 레이어 직접 추출. 디지털 조판 PDF에서 빠르고 충분한 결과를 제공합니다.
2. **2차 시도 (DocStruct OCR):** 품질 점수가 임계값 미만일 때 활성화됩니다. 각 페이지를 래스터 이미지로 렌더링한 뒤 Tesseract OCR을 적용하여 스캔본 또는 이미지 기반 PDF에서 텍스트를 복원합니다.

품질 점수는 5개 신호를 집계합니다:

| 신호 | 가중치 | 근거 |
|------|--------|------|
| 페이지당 문자 수 | 30점 | 콘텐츠 밀도의 대리 지표; 낮은 점수는 이미지 전용 페이지를 시사함 |
| 공백 제외 문자 비율 | 20점 | 과도한 패딩이나 레이아웃 아티팩트가 포함된 페이지 감지 |
| 출력 가능 문자 비율 | 20점 | 유효 텍스트와 OCR 노이즈 또는 바이너리 데이터를 구별 |
| 학술 키워드 적중 | 20점 | 구조적 마커(*abstract*, *introduction*, *references* 등)의 존재 여부 확인 |
| 페이지 추출 성공률 | 10점 | 비어있지 않은 텍스트가 추출된 페이지의 비율 |

### DocStruct 빌드 (선택 — 스캔본 PDF 전용)

```bash
git submodule update --init --recursive
cargo build --release --manifest-path external/DocStruct/Cargo.toml
pip install "Pillow>=11,<12" pytesseract pdf2image "opencv-python>=4.8,<5" numpy
```

바이너리가 없으면 자동으로 pypdf 경로로 폴백합니다.

---

## 요약 생성

paper-farm은 **map-reduce** 전략을 통해 논문의 모든 섹션에 걸쳐 균등한 커버리지를 제공하는 요약을 생성합니다. 단일 패스 방식은 단일 컨텍스트 창의 한계로 인해 방법론 및 실험 섹션 등 분량이 많은 부분을 잘라낼 수밖에 없는 반면, map-reduce는 이를 근본적으로 해결합니다.

**Map 단계.** 설정된 임계값(기본값: 2,000자)을 초과하는 각 섹션에 대해 개별 LLM 호출을 통해 해당 섹션을 약 150단어로 압축합니다. 프롬프트는 해당 섹션의 핵심 기여, 방법론, 정량적 결과, 명시된 한계를 추출하도록 지시합니다. 짧은 섹션은 원문 그대로 전달됩니다.

**Reduce 단계.** 압축된 섹션 텍스트를 연결하여 단일 구조화 추출 호출로 LLM에 제출합니다. 모델은 `summary`, `problem`, `key_idea`, `method`, `experiment`, `results`, `contributions`, `limitations`, `future_work`, `keywords`의 10개 필드를 포함하는 JSON 객체를 출력하며, 출력 언어에 관계없이 기술 용어는 영어를 유지하는 엄격한 규칙을 따릅니다.

이 설계는 *커버리지*(map)와 *종합*(reduce)을 분리함으로써, reduce 호출의 컨텍스트 길이를 증가시키지 않고도 방법론·실험 섹션이 밀도 높은 논문에 대한 요약 충실도를 향상시킵니다.

`experiment` 필드는 `dataset`, `simulator`, `metric` 키를 갖는 중첩 JSON 객체로, 코퍼스 전체에 걸친 구조화된 질의를 가능하게 합니다.

---

## 프로젝트 구조

```
src/paper_farm/
  cli.py            CLI 진입점 (Typer)
  config.py         설정 — paper-farm.toml에서 로드
  pipeline/         PipelineService: ingest → parse → summarize → export
  extractors/       SmartExtractor, SimpleTextExtractor, DocStructExtractor
  normalizers/      텍스트 정제 및 섹션 경계 감지
  summarizers/      OllamaSummaryBackend (map-reduce), LocalSummaryBackend (규칙 기반)
  exporters/        Obsidian Markdown + metadata.json 출력
  watchers/         ZoteroWatcher — 스캐너 스레드 + 워커 큐
  storage/          파일 기반 저장소 (data/)
data/               파이프라인 캐시 — git 제외 (.gitignore 참고)
scripts/            셸 헬퍼: start-watch.sh, monitor.sh, sync.sh
external/DocStruct  OCR 서브모듈 (Rust + Tesseract)
```

---

## 개발

```bash
uv sync
uv run pytest
```
