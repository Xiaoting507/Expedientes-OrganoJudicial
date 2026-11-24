"""HU-10 (Sprint 7): adjuntar documentos PDF al expediente con su huella SHA-256.

Como Secretario, Juez o Abogado de parte quiero adjuntar el PDF de un escrito o resolución
al expediente para que quede en el expediente digital y se pueda probar que no fue alterado.

Reglas:
- RN-10.1 Solo PDF (se revisa la firma %PDF- del archivo, no solo la extensión) y máximo MAX_PDF_MB.
- RN-10.2 Se guarda la huella SHA-256; al descargar se recalcula y, si no coincide, se responde 409
  y queda registrado DOCUMENTO_ALTERADO en la bitácora.
- RN-10.3 Mismos permisos que ver el expediente; el abogado solo en sus casos y no en expedientes cerrados.
  Un expediente archivado no admite documentos nuevos.
- RN-10.4 Cada subida y descarga queda en la bitácora con el hash del archivo.
"""
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import audit
from ..config import DOCUMENTOS_DIR, MAX_PDF_MB
from ..db import get_db
from ..models import Documento, EstadoExpediente, Rol, Usuario
from ..schemas import DocumentoOut, VerificacionDocumentoOut
from ..security import requiere_rol
from .expedientes import CERRADOS, TODOS, obtener_expediente

router = APIRouter(prefix="/api/expedientes", tags=["documentos (HU-10)"])

MAX_BYTES = MAX_PDF_MB * 1024 * 1024
_FIRMA_PDF = b"%PDF-"


def _carpeta() -> Path:
    carpeta = Path(DOCUMENTOS_DIR)
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _ruta(sha256: str) -> Path:
    return _carpeta() / f"{sha256}.pdf"  # el nombre es la huella: no hay rutas controladas por el usuario


def _nombre_seguro(nombre: str | None) -> str:
    base = Path(nombre or "documento.pdf").name
    base = re.sub(r"[^\w.\- ()áéíóúñÁÉÍÓÚÑ]", "_", base).strip() or "documento.pdf"
    return base[:150] if base.lower().endswith(".pdf") else f"{base[:146]}.pdf"


def _huella(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _documento(db: Session, exp_id: int, doc_id: int) -> Documento:
    doc = db.get(Documento, doc_id)
    if doc is None or doc.expediente_id != exp_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return doc


@router.post("/{exp_id}/documentos", response_model=DocumentoOut, status_code=201)
async def subir(
    exp_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_rol(Rol.secretario, Rol.juez, Rol.abogado)),
):
    exp = obtener_expediente(db, exp_id, usuario)
    if exp.estado == EstadoExpediente.archivado or (usuario.rol == Rol.abogado and exp.estado in CERRADOS):
        raise HTTPException(status.HTTP_409_CONFLICT, "El expediente está cerrado y no admite documentos nuevos")

    contenido = await archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"El PDF supera {MAX_PDF_MB} MB")
    if not contenido.startswith(_FIRMA_PDF):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Solo se aceptan archivos PDF")

    sha256 = hashlib.sha256(contenido).hexdigest()
    ruta = _ruta(sha256)
    if not ruta.exists():
        ruta.write_bytes(contenido)
    doc = Documento(expediente_id=exp.id, nombre=_nombre_seguro(archivo.filename), tamano=len(contenido),
                    sha256=sha256, subido_por=usuario.id)
    db.add(doc)
    db.flush()
    audit.registrar(db, usuario=usuario.username, accion="SUBIR_DOCUMENTO", entidad="documento", entidad_id=doc.id,
                    despues={"nombre": doc.nombre, "sha256": sha256, "tamano": doc.tamano},
                    expediente_id=exp.id, request=request)
    db.commit()
    return doc


@router.get("/{exp_id}/documentos", response_model=list[DocumentoOut])
def listar(exp_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*TODOS))):
    exp = obtener_expediente(db, exp_id, usuario)
    return db.query(Documento).filter(Documento.expediente_id == exp.id).order_by(Documento.id.desc()).all()


@router.get("/{exp_id}/documentos/{doc_id}/verificar", response_model=VerificacionDocumentoOut)
def verificar(exp_id: int, doc_id: int, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*TODOS))):
    obtener_expediente(db, exp_id, usuario)
    doc = _documento(db, exp_id, doc_id)
    ruta = _ruta(doc.sha256)
    actual = _huella(ruta) if ruta.exists() else None
    return VerificacionDocumentoOut(integro=actual == doc.sha256, sha256_guardado=doc.sha256, sha256_actual=actual)


@router.get("/{exp_id}/documentos/{doc_id}")
def descargar(exp_id: int, doc_id: int, request: Request, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*TODOS))):
    exp = obtener_expediente(db, exp_id, usuario)
    doc = _documento(db, exp_id, doc_id)
    ruta = _ruta(doc.sha256)
    actual = _huella(ruta) if ruta.exists() else None
    if actual != doc.sha256:
        audit.registrar(db, usuario=usuario.username, accion="DOCUMENTO_ALTERADO", entidad="documento",
                        entidad_id=doc.id, antes={"sha256": doc.sha256}, despues={"sha256": actual},
                        expediente_id=exp.id, request=request)
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "El archivo no coincide con su huella SHA-256: fue alterado o falta. Se registró en la bitácora.")
    audit.registrar(db, usuario=usuario.username, accion="DESCARGAR_DOCUMENTO", entidad="documento",
                    entidad_id=doc.id, despues={"sha256": doc.sha256}, expediente_id=exp.id, request=request)
    db.commit()
    return FileResponse(ruta, media_type="application/pdf", filename=doc.nombre,
                        headers={"X-Content-SHA256": doc.sha256, "Cache-Control": "no-store"})
