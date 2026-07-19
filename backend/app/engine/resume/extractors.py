"""
Deterministic extraction — step 1 of the hybrid pipeline. No semantic
interpretation here, just raw text + basic structural signals
(page count) that later steps use.
"""

import io

import pdfplumber
from docx import Document

from app.engine.resume.schema import ErrorCode, RejectionError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB, per contract's FILE_TOO_LARGE code


class ExtractedText:
    def __init__(self, text: str, pages_detected: int, ocr_used: bool = False):
        self.text = text
        self.pages_detected = pages_detected
        self.ocr_used = ocr_used


def extract_text(file_bytes: bytes, file_format: str) -> ExtractedText:
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise RejectionError(
            ErrorCode.FILE_TOO_LARGE,
            f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024*1024)}MB limit.",
        )

    if file_format == "pdf":
        return _extract_pdf(file_bytes)
    elif file_format == "docx":
        return _extract_docx(file_bytes)
    else:
        raise RejectionError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"Unsupported file format '{file_format}'. Only 'pdf' and 'docx' are supported.",
        )


def _extract_pdf(file_bytes: bytes) -> ExtractedText:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                pages_text.append(page_text)
            full_text = "\n".join(pages_text)
            pages_detected = len(pdf.pages)
    except RejectionError:
        raise
    except Exception as e:
        # Confirmed via real-file testing with an actual encrypted PDF:
        # pdfplumber/pdfminer raise PdfminerException wrapping
        # PDFPasswordIncorrect, and str(e) is EMPTY — message-sniffing
        # does not work. Check the exception's type name and repr
        # instead, which reliably contain "password".
        diagnostic = f"{type(e).__name__} {repr(e)}".lower()
        if "password" in diagnostic or "encrypt" in diagnostic:
            raise RejectionError(
                ErrorCode.PASSWORD_PROTECTED,
                "This PDF is password-protected and cannot be read.",
            )
        raise RejectionError(
            ErrorCode.CORRUPTED_FILE, f"Could not open or parse this PDF: {e}"
        )

    # Little to no extractable text usually means a scanned/image-based
    # PDF. v0.1 has no OCR — this is a recoverable condition, not a
    # rejection, per the contract's Error Contract table.
    ocr_used = False
    if len(full_text.strip()) < 20:
        ocr_used = (
            False  # explicitly false: we did NOT run OCR, we just got little text
        )

    return ExtractedText(
        text=full_text, pages_detected=pages_detected, ocr_used=ocr_used
    )


def _extract_docx(file_bytes: bytes) -> ExtractedText:
    try:
        doc = Document(io.BytesIO(file_bytes))
        full_text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise RejectionError(
            ErrorCode.CORRUPTED_FILE, f"Could not open or parse this DOCX file: {e}"
        )

    # DOCX has no fixed "pages" concept without rendering — approximate
    # with 1 if there's any content, 0 if empty. Documented limitation.
    pages_detected = 1 if full_text.strip() else 0
    return ExtractedText(text=full_text, pages_detected=pages_detected, ocr_used=False)
