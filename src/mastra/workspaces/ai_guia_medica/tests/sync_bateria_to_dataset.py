"""
Sincroniza los 100 casos de bateria_100_preguntas.py al dataset Mastra
"Guia médica Dataset" (LibSQL vía API local de Studio).

Uso:
    python tests/sync_bateria_to_dataset.py
    python tests/sync_bateria_to_dataset.py --url http://localhost:4111
    python tests/sync_bateria_to_dataset.py --keep-existing   # no borra items previos
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from bateria_100_preguntas import CASOS, Caso

DATASET_NAME = "Guia médica Dataset"
SOURCE_REF = "bateria_100_preguntas.py"


def infer_herramienta(caso: Caso) -> str:
    if caso.herramienta_esperada:
        return caso.herramienta_esperada

    prefijo = caso.categoria.split("-", 1)[0]
    pregunta = caso.pregunta.lower()

    if prefijo == "A":
        return "buscarProfesionales"
    if prefijo == "B":
        return "mapearSintoma"
    if prefijo == "C":
        if "especialidad" in pregunta:
            return "listarEspecialidades"
        return "buscarProfesionales"
    if prefijo in ("D", "E"):
        return "buscarProfesionales"
    return ""


def caso_to_item(caso: Caso) -> dict:
    herramienta = infer_herramienta(caso)
    ground_truth: dict = {
        "casoId": caso.id,
        "categoria": caso.categoria,
        "palabras_clave": caso.palabras_clave,
        "sin_resultado_ok": caso.sin_resultado_ok,
    }
    if herramienta:
        ground_truth["herramienta"] = herramienta

    # Experiments call agent.generate(item.input, options) — the first arg IS messages,
    # not { messages: "..." }. Use a plain string (or [{role, content}]).
    item: dict = {
        "input": caso.pregunta,
        "groundTruth": ground_truth,
        "metadata": {"bateriaCasoId": caso.id},
        "source": {"type": "json", "referenceId": SOURCE_REF},
    }

    if caso.categoria.startswith("B-"):
        steps = [{"name": "mapearSintoma", "stepType": "tool_call"}]
        if herramienta == "mapearSintoma":
            steps.append({"name": "buscarProfesionales", "stepType": "tool_call"})
        item["expectedTrajectory"] = {"steps": steps, "ordering": "relaxed"}

    return item


def api_request(
    base_url: str,
    method: str,
    path: str,
    *,
    query: dict | None = None,
    body: dict | None = None,
) -> dict:
    url = f"{base_url}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc


def _list_key(body: dict, primary: str, fallback: str) -> list:
    return body.get(primary) or body.get(fallback) or []


def _pagination(body: dict) -> dict:
    return body.get("pagination") or body.get("page") or {}


def find_dataset_id(base_url: str) -> str:
    body = api_request(base_url, "GET", "/api/datasets", query={"page": 0, "perPage": 50})
    for ds in _list_key(body, "datasets", "data"):
        if ds.get("name") == DATASET_NAME:
            return ds["id"]
    raise RuntimeError(f'Dataset "{DATASET_NAME}" no encontrado. Créalo en Mastra Studio.')


def list_all_item_ids(base_url: str, dataset_id: str) -> list[str]:
    ids: list[str] = []
    page = 0
    per_page = 100
    while True:
        body = api_request(
            base_url,
            "GET",
            f"/api/datasets/{dataset_id}/items",
            query={"page": page, "perPage": per_page},
        )
        ids.extend(item["id"] for item in _list_key(body, "items", "data"))
        if not _pagination(body).get("hasMore", False):
            break
        page += 1
    return ids


def delete_items(base_url: str, dataset_id: str, item_ids: list[str]) -> None:
    if not item_ids:
        return
    api_request(
        base_url,
        "DELETE",
        f"/api/datasets/{dataset_id}/items/batch",
        body={"itemIds": item_ids},
    )


def add_items_batch(base_url: str, dataset_id: str, items: list[dict], chunk_size: int = 50) -> int:
    total = 0
    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        body = api_request(
            base_url,
            "POST",
            f"/api/datasets/{dataset_id}/items/batch",
            body={"items": chunk},
        )
        total += body.get("count", len(chunk))
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync batería 100 → Mastra dataset")
    parser.add_argument("--url", default="http://localhost:4111", help="URL del servidor Mastra dev")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="No borrar items existentes antes de importar",
    )
    args = parser.parse_args()

    items = [caso_to_item(c) for c in CASOS]
    assert len(items) == 100

    try:
        dataset_id = find_dataset_id(args.url)
        if not args.keep_existing:
            existing = list_all_item_ids(args.url, dataset_id)
            if existing:
                delete_items(args.url, dataset_id, existing)
                print(f"Eliminados {len(existing)} items previos")
        added = add_items_batch(args.url, dataset_id, items)
        body = api_request(
            args.url,
            "GET",
            f"/api/datasets/{dataset_id}/items",
            query={"page": 0, "perPage": 1},
        )
        total = _pagination(body).get("total", added)
    except (urllib.error.URLError, RuntimeError) as exc:
        print(f"ERROR API: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Dataset: {DATASET_NAME} ({dataset_id})")
    print(f"Items importados: {added}")
    print(f"Total en dataset: {total}")
    print(f"Ver en Studio: {args.url} → Datasets → {DATASET_NAME}")


if __name__ == "__main__":
    main()
