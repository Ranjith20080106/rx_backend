import io
import logging
from fastapi import UploadFile, HTTPException

logger = logging.getLogger("TextExtractor")

# Try to import pdfplumber and python-docx, with graceful fallbacks
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    logger.warning("pdfplumber not available. PDF text extraction will fall back to simple string matching.")

try:
    import docx
except ImportError:
    docx = None
    logger.warning("python-docx not available. Word text extraction will fall back.")

def extract_text_from_file(file: UploadFile) -> str:
    """Read an uploaded file and extract its text content depending on file type (PDF/DOCX)."""
    filename = file.filename.lower()
    content = file.file.read()
    
    # Always seek back to beginning of file stream just in case
    file.file.seek(0)
    
    if filename.endswith(".pdf"):
        return extract_from_pdf(content)
    elif filename.endswith(".docx"):
        return extract_from_docx(content)
    elif filename.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload PDF, DOCX, or TXT file types."
        )

def extract_from_pdf(content_bytes: bytes) -> str:
    """Extract raw text from a PDF stream using pdfplumber."""
    if not pdfplumber:
        # Fallback raw decode if library not present
        return content_bytes.decode("utf-8", errors="ignore")
        
    text = ""
    try:
        pdf_file = io.BytesIO(content_bytes)
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        # Try fallback raw conversion
        try:
            return content_bytes.decode("utf-8", errors="ignore")
        except:
            raise HTTPException(status_code=500, detail=f"Failed to parse PDF document: {str(e)}")

def extract_from_docx(content_bytes: bytes) -> str:
    """Extract raw text from a DOCX stream using python-docx."""
    if not docx:
        return content_bytes.decode("utf-8", errors="ignore")
        
    try:
        docx_file = io.BytesIO(content_bytes)
        doc = docx.Document(docx_file)
        fullText = []
        for para in doc.paragraphs:
            fullText.append(para.text)
        return '\n'.join(fullText)
    except Exception as e:
        logger.error(f"Error parsing Word Document: {e}")
        try:
            return content_bytes.decode("utf-8", errors="ignore")
        except:
            raise HTTPException(status_code=500, detail=f"Failed to parse Word Document: {str(e)}")
