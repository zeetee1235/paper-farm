# paper-farm 사용 가이드 (한국어)

이 문서는 `paper-farm`의 전체 파이프라인을 한국어로 정리한 실사용 가이드입니다.

## 1. 이 프로젝트가 하는 일

논문 PDF를 받아 아래 순서로 처리합니다.

1. `ingest`: PDF 등록 + 메타데이터 생성
2. `extract`: 본문 추출 (기본 `DocStruct`, 실패 시 `SimpleText` 폴백)
3. `normalize`: 정리된 섹션/텍스트 생성
4. `summarize --mode agent-pr`: 외부 에이전트 전달용 패키지 생성
5. Obsidian 폴더로 결과 동기화

핵심 결과물:

- `agent.md`: 에이전트가 읽을 단일 핸드오프 문서
- `paper.pdf`: 원문 PDF
- `metadata.json`: 논문 메타데이터
- `note.agent.md`: 에이전트가 생성한 옵시디언 노트(생성 시)

## 2. 폴더 구조 (현재 기본값)

프로젝트 내부 Obsidian 구조:

- `obsidian/vault/00_Inbox_PDFs/`  
  새 PDF를 넣는 폴더
- `obsidian/vault/00_Inbox_PDFs/_processed/`  
  처리 완료된 PDF 자동 이동 폴더
- `obsidian/vault/10_Papers/<paper_id>/`  
  옵시디언용 정리 산출물 폴더

파이프라인 원본 아티팩트:

- `data/papers/<paper_id>/...`

## 3. 최초 1회 셋업

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

DocStruct 서브모듈 + 빌드:

```bash
git submodule update --init --recursive
cargo build --release --manifest-path external/DocStruct/Cargo.toml
```

DocStruct OCR 파이썬 의존성:

```bash
.venv/bin/pip install numpy "Pillow>=11,<12" pytesseract pdf2image "opencv-python>=4.8,<5"
```

## 4. 가장 쉬운 사용법 (권장)

### A. 수동 1회 처리

1. PDF를 `obsidian/vault/00_Inbox_PDFs/`에 복사
2. 아래 실행:

```bash
scripts/obsidian_auto_add.sh --once
```

결과:

- `obsidian/vault/10_Papers/<paper_id>/` 생성
- 원본 PDF는 `_processed`로 이동

### B. 자동 감시 모드

```bash
scripts/obsidian_auto_add.sh
```

실행 중에는 Inbox 폴더에 PDF 넣기만 하면 주기적으로 자동 처리합니다.

## 5. 스크립트별 역할

### `scripts/agent_package_batch.sh`

- PDF 파일/폴더를 받아 일괄 처리
- 인자 없이 실행하면 Inbox(`obsidian/vault/00_Inbox_PDFs`)를 스캔
- 처리 후 Obsidian 폴더로 동기화

예시:

```bash
scripts/agent_package_batch.sh
scripts/agent_package_batch.sh /path/to/pdfs
scripts/agent_package_batch.sh a.pdf b.pdf
```

### `scripts/obsidian_auto_add.sh`

- 내부적으로 `agent_package_batch.sh`를 반복 호출
- `--once`: 1회 실행 후 종료
- 기본: 무한 루프 감시

## 6. 외부 에이전트 연결 방식

`summarize --mode agent-pr`를 돌리면 아래가 생성됩니다.

- `data/papers/<paper_id>/agent_package/agent.md`
- `.../prompt.txt`
- `.../summary_request.json`
- `.../output_contract.json`

실무에서는 보통 `agent.md` 하나만 외부 에이전트에 전달하면 됩니다.

에이전트가 같은 폴더에 생성해야 할 결과:

- `summary.agent.json`
- `note.agent.md`

`note.agent.md`가 만들어지면 다음 배치/자동 처리 때 Obsidian 폴더에도 동기화됩니다.

## 7. 수동 파이프라인 명령 (디버깅용)

```bash
paper-farm ingest <pdf_path>
paper-farm extract <paper_id>
paper-farm normalize <paper_id>
paper-farm summarize <paper_id> --mode agent-pr
paper-farm show <paper_id>
```

## 8. 자주 쓰는 환경변수

- `DOCSTRUCT_BIN`: DocStruct 실행 파일 경로
- `DOCSTRUCT_PYTHON`: DocStruct OCR에 사용할 Python 경로
- `DOCSTRUCT_DPI`: OCR DPI (기본 120)
- `DOCSTRUCT_TIMEOUT_SEC`: DocStruct 처리 제한 시간(초)
- `LOOP_INTERVAL_SEC`: 자동 감시 주기 초 (기본 20)

## 9. 문제 발생 시 체크리스트

1. `.venv` 활성화 여부
2. DocStruct 빌드 여부 (`external/DocStruct/target/release/docstruct`)
3. `tesseract`, `pdftoppm(poppler)` 설치 여부
4. Inbox 경로에 실제 PDF가 있는지
5. `paper-farm show <paper_id>`로 아티팩트 존재 확인
