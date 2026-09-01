"""
Struttura territoriale Puglia: 6 province/enti + 257 comuni.
Dati allineati con i totali ufficiali della Regione Puglia.
"""

from typing import Any

PUGLIA: dict[str, Any] = {
    "regione": "Puglia",
    "province": [
        {
            "nome": "Bari",
            "sigla": "BA",
            "comuni": [
                "Acquaviva delle Fonti", "Adelfia", "Alberobello", "Altamura", "Bari",
                "Binetto", "Bitetto", "Bitonto", "Bitritto", "Capurso", "Casamassima",
                "Cassano delle Murge", "Castellana Grotte", "Cellamare", "Conversano",
                "Corato", "Gioia del Colle", "Giovinazzo", "Gravina in Puglia", "Grumo Appula",
                "Locorotondo", "Modugno", "Mola di Bari", "Molfetta", "Monopoli",
                "Noci", "Noicattaro", "Palo del Colle", "Poggiorsini", "Polignano a Mare",
                "Putignano", "Rutigliano", "Ruvo di Puglia", "Sammichele di Bari",
                "Sannicandro di Bari", "Santeramo in Colle", "Terlizzi", "Toritto",
                "Triggiano", "Turi", "Valenzano",
            ],
        },
        {
            "nome": "Barletta-Andria-Trani",
            "sigla": "BT",
            "comuni": [
                "Andria", "Barletta", "Bisceglie", "Canosa di Puglia", "Margherita di Savoia",
                "Minervino Murge", "San Ferdinando di Puglia", "Spinazzola", "Trani", "Trinitapoli",
            ],
        },
        {
            "nome": "Brindisi",
            "sigla": "BR",
            "comuni": [
                "Brindisi", "Carovigno", "Ceglie Messapica", "Cellino San Marco", "Cisternino",
                "Erchie", "Fasano", "Francavilla Fontana", "Latiano", "Mesagne",
                "Oria", "Ostuni", "San Donaci", "San Michele Salentino", "San Pancrazio Salentino",
                "San Pietro Vernotico", "San Vito dei Normanni", "Torchiarolo", "Torre Santa Susanna",
                "Villa Castelli",
            ],
        },
        {
            "nome": "Foggia",
            "sigla": "FG",
            "comuni": [
                "Accadia", "Alberona", "Anzano di Puglia", "Apricena", "Ascoli Satriano",
                "Biccari", "Bovino", "Cagnano Varano", "Candela", "Carapelle",
                "Carlantino", "Carpino", "Casalnuovo Monterotaro", "Casalvecchio di Puglia",
                "Castelluccio dei Sauri", "Castelluccio Valmaggiore", "Castelnuovo della Daunia",
                "Celenza Valfortore", "Celle di San Vito", "Cerignola", "Chieuti",
                "Deliceto", "Faeto", "Foggia", "Ischitella", "Isole Tremiti",
                "Lesina", "Lucera", "Manfredonia", "Mattinata", "Monte Sant'Angelo",
                "Monteleone di Puglia", "Motta Montecorvino", "Ordona", "Orsara di Puglia",
                "Orta Nova", "Panni", "Peschici", "Pietramontecorvino", "Poggio Imperiale",
                "Rignano Garganico", "Rocchetta Sant'Antonio", "Rodi Garganico", "Roseto Valfortore",
                "San Giovanni Rotondo", "San Marco in Lamis", "San Marco la Catola",
                "San Nicandro Garganico", "San Paolo di Civitate", "San Severo",
                "Sant'Agata di Puglia", "Serracapriola", "Stornara", "Stornarella",
                "Torremaggiore", "Troia", "Vico del Gargano", "Vieste", "Volturara Appula",
                "Volturino", "Zapponeta",
            ],
        },
        {
            "nome": "Lecce",
            "sigla": "LE",
            "comuni": [
                "Acquarica del Capo", "Alessano", "Alezio", "Alliste", "Andrano",
                "Aradeo", "Arnesano", "Bagnolo del Salento", "Botrugno", "Calimera",
                "Campi Salentina", "Cannole", "Caprarica di Lecce", "Carmiano", "Carpignano Salentino",
                "Casarano", "Castri di Lecce", "Castrignano de' Greci", "Castrignano del Capo",
                "Castro", "Cavallino", "Collepasso", "Copertino", "Corigliano d'Otranto",
                "Corsano", "Cursi", "Cutrofiano", "Diso", "Gagliano del Capo",
                "Galatina", "Galatone", "Gallipoli", "Giuggianello", "Giurdignano",
                "Guagnano", "Lecce", "Leverano", "Lizzanello", "Maglie",
                "Martano", "Martignano", "Matino", "Melendugno", "Melissano",
                "Melpignano", "Miggiano", "Minervino di Lecce", "Monteroni di Lecce",
                "Montesano Salentino", "Morciano di Leuca", "Muro Leccese", "Nardò",
                "Neviano", "Nociglia", "Novoli", "Ortelle", "Otranto",
                "Palmariggi", "Parabita", "Patù", "Poggiardo", "Porto Cesareo",
                "Presicce-Acquarica", "Racale", "Ruffano", "Salice Salentino", "Salve",
                "San Cassiano", "San Cesario di Lecce", "San Donato di Lecce", "San Pietro in Lama",
                "Sanarica", "Sannicola", "Santa Cesarea Terme", "Scorrano", "Seclì",
                "Sogliano Cavour", "Soleto", "Specchia", "Spongano", "Squinzano",
                "Sternatia", "Supersano", "Surano", "Surbo", "Taurisano",
                "Taviano", "Tiggiano", "Trepuzzi", "Tricase", "Tuglie",
                "Ugento", "Uggiano la Chiesa", "Veglie", "Vernole", "Zollino",
            ],
        },
        {
            "nome": "Taranto",
            "sigla": "TA",
            "comuni": [
                "Avetrana", "Carosino", "Castellaneta", "Crispiano", "Faggiano",
                "Fragagnano", "Ginosa", "Grottaglie", "Laterza", "Leporano",
                "Lizzano", "Manduria", "Martina Franca", "Maruggio", "Massafra",
                "Monteiasi", "Montemesola", "Monteparano", "Mottola", "Palagianello",
                "Palagiano", "Pulsano", "Roccaforzata", "San Giorgio Ionico", "San Marzano di San Giuseppe",
                "Sava", "Statte", "Taranto", "Torricella",
            ],
        },
    ],
}


def conta_comuni() -> int:
    return sum(len(p["comuni"]) for p in PUGLIA["province"])


def get_territorio() -> dict[str, Any]:
    return {
        "regione": PUGLIA["regione"],
        "totale_comuni": conta_comuni(),
        "province": [
            {
                "nome": p["nome"],
                "sigla": p["sigla"],
                "n_comuni": len(p["comuni"]),
                "comuni": sorted(p["comuni"]),
            }
            for p in PUGLIA["province"]
        ],
    }


def comuni_di_provincia(provincia: str) -> list[str]:
    for p in PUGLIA["province"]:
        if p["nome"].lower() == provincia.lower() or p["sigla"].lower() == provincia.lower():
            return sorted(p["comuni"])
    return []
