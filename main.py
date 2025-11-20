from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from uuid import uuid4
from datetime import datetime

app = FastAPI(
    title="Saga Core API Backend",
    description=(
        "En enkel in-memory backend for Saga Core API. "
        "Ikke produksjonsklar, men egnet til testing via Kong."
    ),
    version="0.1.0",
)

# -----------------------------
# Pydantic-modeller (tilpasset OpenAPI-specen din)
# -----------------------------


class NewCase(BaseModel):
    title: str = Field(..., description="Tittel på saken")
    description: Optional[str] = Field(None, description="Beskrivelse av saken")
    externalRef: Optional[str] = Field(
        None, description="F.eks. nemnd-/tingsrettsreferanse"
    )


class Case(NewCase):
    id: str
    createdAt: datetime


class NewDocument(BaseModel):
    type: str = Field(..., description='f.eks. "vedtak", "journal", "transkripsjon"')
    content: str = Field(..., description="Råtekst eller allerede OCR-et tekst")
    source: Optional[str] = Field(None, description="Filnavn, system eller kilde")


class Document(NewDocument):
    id: str
    createdAt: datetime


class TimelineItem(BaseModel):
    date: str
    description: str


class FullAnalysis(BaseModel):
    caseId: str
    generatedAt: datetime
    timeline: List[TimelineItem] = []
    themes: List[str] = []
    riskFlags: List[str] = []
    medicalizationFindings: List[str] = []
    powerLanguageFindings: List[str] = []
    legalReferences: List[str] = []


class LegalSearchRequest(BaseModel):
    text: str
    domain: Optional[str] = Field(
        None, description='f.eks. "barnevern", "helse", "skole"'
    )


class LegalReferenceMatch(BaseModel):
    law: str
    section: str
    relevanceScore: float


class LegalSearchResponse(BaseModel):
    matches: List[LegalReferenceMatch] = []


# -----------------------------
# In-memory "database"
# -----------------------------

cases_store: Dict[str, Case] = {}
documents_store: Dict[str, List[Document]] = {}
analysis_store: Dict[str, FullAnalysis] = {}


# -----------------------------
# Endepunkter
# -----------------------------


@app.post("/cases", response_model=Case, status_code=201)
def create_case(new_case: NewCase):
    """
    Opprett ny sak.
    """
    case_id = str(uuid4())
    case = Case(
        id=case_id,
        title=new_case.title,
        description=new_case.description,
        externalRef=new_case.externalRef,
        createdAt=datetime.utcnow(),
    )
    cases_store[case_id] = case
    documents_store.setdefault(case_id, [])
    return case


@app.get("/cases/{caseId}", response_model=Case)
def get_case(caseId: str):
    """
    Hent informasjon om en sak.
    """
    case = cases_store.get(caseId)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/cases/{caseId}/documents", response_model=Document, status_code=201)
def upload_document(caseId: str, new_doc: NewDocument):
    """
    Last opp dokument til en sak.
    """
    if caseId not in cases_store:
        raise HTTPException(status_code=404, detail="Case not found")

    doc_id = str(uuid4())
    doc = Document(
        id=doc_id,
        type=new_doc.type,
        content=new_doc.content,
        source=new_doc.source,
        createdAt=datetime.utcnow(),
    )
    documents_store.setdefault(caseId, []).append(doc)
    return doc


@app.get("/cases/{caseId}/documents", response_model=List[Document])
def list_documents(caseId: str):
    """
    List dokumenter i en sak.
    """
    if caseId not in cases_store:
        raise HTTPException(status_code=404, detail="Case not found")
    return documents_store.get(caseId, [])


@app.post("/cases/{caseId}/analysis/full", status_code=202)
def run_full_analysis(caseId: str):
    """
    Start full analyse av dokumentene i saken.
    Her er det i praksis en synkron, enkel mock-analyse.
    """
    if caseId not in cases_store:
        raise HTTPException(status_code=404, detail="Case not found")

    docs = documents_store.get(caseId, [])

    # Veldig enkel "analyse" som placeholder
    timeline = [
        TimelineItem(
            date=doc.createdAt.isoformat(),
            description=f"Dokument {doc.id} ({doc.type}) lastet opp",
        )
        for doc in docs
    ]

    analysis = FullAnalysis(
        caseId=caseId,
        generatedAt=datetime.utcnow(),
        timeline=timeline,
        themes=["mock-theme: dokumentopplasting"],
        riskFlags=[],
        medicalizationFindings=[],
        powerLanguageFindings=[],
        legalReferences=[],
    )

    analysis_store[caseId] = analysis
    return {"status": "analysis_started", "caseId": caseId}


@app.get("/cases/{caseId}/analysis/full", response_model=FullAnalysis)
def get_full_analysis(caseId: str):
    """
    Hent sist gjennomførte fullanalyse.
    """
    analysis = analysis_store.get(caseId)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this case")
    return analysis


@app.post("/legal/references/search", response_model=LegalSearchResponse)
def search_legal_references(req: LegalSearchRequest):
    """
    Mock: foreslå relevante lovhenvisninger.
    I produksjon ville dette kalle Lovdata-proxy / annen juristlogikk.
    """
    text = req.text.lower()
    domain = (req.domain or "").lower()

    matches: List[LegalReferenceMatch] = []

    # Enkle, naive regler bare for demo/testing:
    if "barnevern" in text or domain == "barnevern":
        matches.append(
            LegalReferenceMatch(
                law="Barnevernsloven", section="§ 1-3", relevanceScore=0.9
            )
        )
        matches.append(
            LegalReferenceMatch(
                law="Barnevernsloven", section="§ 4-1", relevanceScore=0.8
            )
        )

    if "helse" in text or domain == "helse":
        matches.append(
            LegalReferenceMatch(
                law="Helsepersonelloven", section="§ 4", relevanceScore=0.85
            )
        )

    # Hvis ingenting ble trigget, returner tom liste
    return LegalSearchResponse(matches=matches)