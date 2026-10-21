import re

import sqlparse


def analyze_sql(sql_text):
    normalized = sql_text.strip()
    statements = [statement.strip() for statement in sqlparse.split(normalized) if statement.strip()]
    checks = []
    recommendations = []
    score = 100

    def add_check(label, ok, detail, recommendation=None, penalty=10):
        nonlocal score
        checks.append({"label": label, "ok": ok, "detail": detail})
        if not ok:
            score = max(0, score - penalty)
            if recommendation:
                recommendations.append(recommendation)

    add_check(
        "Fichier non vide",
        bool(normalized),
        f"{len(statements)} instruction(s) détectée(s)." if normalized else "Aucune instruction SQL détectée.",
        "Ajoutez au moins une instruction SQL valide.",
        30,
    )

    has_select_star = bool(re.search(r"\bSELECT\s+\*", normalized, re.IGNORECASE))
    add_check(
        "Colonnes explicites",
        not has_select_star,
        "Aucun SELECT * détecté." if not has_select_star else "SELECT * détecté.",
        "Listez explicitement les colonnes afin de stabiliser le contrat de données et limiter les transferts.",
        8,
    )

    dangerous = any(
        re.search(r"\b(DELETE\s+FROM|UPDATE)\b", statement, re.IGNORECASE)
        and not re.search(r"\bWHERE\b", statement, re.IGNORECASE)
        for statement in statements
    )
    add_check(
        "Écritures filtrées",
        not dangerous,
        "Les UPDATE/DELETE détectés contiennent un filtre." if not dangerous else "UPDATE ou DELETE sans WHERE possible.",
        "Ajoutez une clause WHERE et testez d'abord la sélection correspondante dans une transaction.",
        25,
    )

    has_drop_or_truncate = bool(re.search(r"\b(DROP|TRUNCATE)\b", normalized, re.IGNORECASE))
    add_check(
        "Opérations destructives",
        not has_drop_or_truncate,
        "Aucun DROP/TRUNCATE détecté." if not has_drop_or_truncate else "DROP ou TRUNCATE détecté.",
        "Sauvegardez la base et exigez une validation explicite avant l'exécution.",
        18,
    )

    create_tables = re.findall(
        r"CREATE\s+TABLE[\s\S]*?\((.*?)\)\s*(?:ENGINE|;|$)", normalized, re.IGNORECASE
    )
    tables_without_pk = [block for block in create_tables if not re.search(r"\bPRIMARY\s+KEY\b", block, re.IGNORECASE)]
    add_check(
        "Clés primaires",
        not tables_without_pk,
        "Chaque table créée possède une clé primaire." if not tables_without_pk else f"{len(tables_without_pk)} table(s) sans clé primaire.",
        "Définissez une PRIMARY KEY stable pour chaque table métier.",
        15,
    )

    has_create = bool(re.search(r"\bCREATE\s+TABLE\b", normalized, re.IGNORECASE))
    has_utf8mb4 = bool(re.search(r"\butf8mb4\b", normalized, re.IGNORECASE))
    add_check(
        "Encodage MySQL",
        not has_create or has_utf8mb4,
        "utf8mb4 est déclaré." if has_utf8mb4 else "Aucun encodage utf8mb4 explicite pour les tables créées.",
        "Utilisez DEFAULT CHARSET=utf8mb4 et une collation adaptée pour conserver tous les caractères Unicode.",
        8,
    )

    if re.search(r"\b(WHERE|JOIN)\b", normalized, re.IGNORECASE) and not re.search(r"\bINDEX\b|\bKEY\s*\(", normalized, re.IGNORECASE):
        recommendations.append(
            "Vérifiez avec EXPLAIN que les colonnes souvent utilisées dans WHERE et JOIN disposent d'index adaptés."
        )

    if not recommendations:
        recommendations.append("La vérification statique de base est satisfaisante. Validez encore le script sur une base de test.")

    return {
        "score": score,
        "status": "conforme" if score >= 85 else "à revoir" if score >= 60 else "non conforme",
        "statement_count": len(statements),
        "checks": checks,
        "recommendations": recommendations,
    }


def report_as_prompt(report):
    checks = "\n".join(
        f"- {'OK' if item['ok'] else 'ALERTE'} — {item['label']}: {item['detail']}"
        for item in report["checks"]
    )
    recommendations = "\n".join(f"- {item}" for item in report["recommendations"])
    return (
        f"Rapport automatique SQL: score {report['score']}/100, statut {report['status']}.\n"
        f"Contrôles:\n{checks}\nRecommandations:\n{recommendations}"
    )
