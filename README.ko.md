<img src="docs/logo.png" alt="paper-farm" width="160" align="left" style="margin-right:24px; margin-bottom:4px;" />

# paper-farm

Zotero 스토리지를 자동으로 감시하여 새로운 연구 논문 PDF를 감지하고, 전문을 추출·정제한 뒤 로컬 LLM으로 구조화된 요약을 생성하여 Obsidian 볼트에 Markdown 노트로 저장하는 로컬-퍼스트 파이프라인입니다.

English: [README.md](./README.md)

<br clear="left" />

---

## 개요

<p align="center">
  <img src="docs/pipeline.svg" alt="paper-farm pipeline" width="870"/>
</p>

> **Fig. 1.** 전체 처리 파이프라인. 큐 기반 워처 스레드가 Zotero 스토리지의 새 PDF를 감지하면, 각 논문을 추출 → 정규화 → LLM 요약 → Obsidian 내보내기 순서로 순차 처리합니다.

각 논문은 Obsidian 볼트 내 독립적인 디렉터리를 생성합니다:

```
<obsidian-vault>/
  <paper-id>/
    summary.md      ← LLM이 생성한 구조화 요약 (YAML 프론트매터 포함)
    metadata.json   ← 제목, 저자, 연도, 학회, DOI, 태그
    notes.md        ← 빈 노트 템플릿 (연구 아이디어 / 질문 / 후속 논문)
    paper.pdf       ← 원본 PDF 사본
```

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
scripts/start-watch.sh       # 와처 실행 + logs/ 에 로그 저장
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

## 스마트 추출

<p align="center">
  <img src="docs/extraction.svg" alt="Smart extraction flow" width="500"/>
</p>

> **Fig. 2.** 2단계 추출 전략. pypdf를 먼저 시도하고, 5개 신호로 구성된 품질 점수(최대 100점)가 임계값 60점 미만이면 DocStruct OCR(Rust/Tesseract 기반)로 전환합니다.

| 신호 | 가중치 | 설명 |
|------|--------|------|
| 페이지당 문자 수 | 30점 | 전체 문자 수 ÷ 페이지 수 |
| 공백 제외 문자 비율 | 20점 | 비공백 문자의 비율 |
| 출력 가능 문자 비율 | 20점 | ASCII 출력 가능 문자 비율; OCR 노이즈는 낮게 측정됨 |
| 학술 키워드 적중 | 20점 | *abstract, introduction, references* 등 섹션 제목 존재 여부 |
| 페이지 추출 성공률 | 10점 | 비어있지 않은 텍스트가 추출된 페이지 비율 |

### DocStruct 빌드 (선택 — 스캔본 PDF 전용)

```bash
git submodule update --init --recursive
cargo build --release --manifest-path external/DocStruct/Cargo.toml
pip install "Pillow>=11,<12" pytesseract pdf2image "opencv-python>=4.8,<5" numpy
```

바이너리가 없으면 자동으로 pypdf 경로로 폴백합니다.

---

## 프로젝트 구조

```
src/paper_farm/
  cli.py            CLI 진입점 (Typer)
  config.py         설정 — paper-farm.toml에서 로드
  pipeline/         PipelineService: ingest → parse → summarize → export
  extractors/       SmartExtractor, SimpleTextExtractor, DocStructExtractor
  normalizers/      텍스트 정제 및 섹션 경계 감지
  summarizers/      OllamaSummaryBackend, LocalSummaryBackend (규칙 기반)
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
