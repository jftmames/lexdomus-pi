from dataclasses import dataclass, asdict
from typing import List, Dict

@dataclass
class InquiryNode:
    pregunta: str
    encaje_ref: str  # e.g., 'LPI art. 14'
    principio: str   # e.g., 'favor auctoris'
    evidencias_requeridas: List[str]
    alternativa: str

def decompose_clause(clause: str, jurisdiction: str) -> List[Dict]:
    # TODO: implementar descomposición real (plantilla mínima)
    nodes = [
        InquiryNode(
            pregunta="¿Qué derechos patrimoniales se transfieren?",
            encaje_ref="LPI art. 17-23",
            principio="seguridad jurídica",
            evidencias_requeridas=["Texto cláusula", "Art. concretos"],
            alternativa="Licencia no exclusiva limitada a soportes listados"
        ),
        InquiryNode(
            pregunta="¿Se respetan los derechos morales?",
            encaje_ref="LPI art. 14; Berna art. 6bis",
            principio="favor auctoris",
            evidencias_requeridas=["Referencia expresa a paternidad e integridad"],
            alternativa="Prever autorización previa para modificaciones sustanciales"
        )
    ]
    return [asdict(n) for n in nodes]
