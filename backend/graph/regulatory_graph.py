"""
Regulatory Knowledge Graph
File: backend/graph/regulatory_graph.py

NetworkX directed graph mapping relationships between
RBI circulars, mandates, clauses, and MAPs.

Nodes: mandates, clauses
Edges: AMENDS, REFERENCES, SUPERSEDES, CITES

When a new amendment arrives, graph traversal instantly
finds all existing MAPs affected by the same clause series.

Pre-populated with Canara Bank's documented penalty categories
for demo purposes.
"""

import networkx as nx
from typing import Optional
from sqlalchemy.orm import Session


# ============================================================
# GRAPH INITIALIZATION
# ============================================================

def build_graph(db: Session) -> nx.DiGraph:
    """
    Builds the regulatory knowledge graph from all
    mandates stored in PostgreSQL.

    Also pre-populates with known Canara Bank regulatory
    series relationships for demo purposes.

    Returns:
        nx.DiGraph — directed graph with all relationships
    """
    from backend.models import Mandate, Map

    G = nx.DiGraph()

    # Pre-populate with known Canara Bank regulatory series
    G = _prepopulate_canara_bank_series(G)

    # Add all mandates from database as nodes
    mandates = db.query(Mandate).all()
    for mandate in mandates:
        G = add_mandate_to_graph(G, mandate)

    # Add all MAP nodes and link to their mandates
    maps = db.query(Map).all()
    for map_obj in maps:
        map_node_id = f"MAP:{str(map_obj.id)[:8]}"
        G.add_node(
            map_node_id,
            type            = "MAP",
            map_id          = str(map_obj.id),
            obligation_text = (map_obj.obligation_text or "")[:100],
            priority_tier   = map_obj.priority_tier,
            mpi_score       = float(map_obj.mpi_score or 0),
            status          = map_obj.status,
        )

        # Link MAP to its parent mandate
        mandate_node_id = f"MANDATE:{str(map_obj.mandate_id)[:8]}"
        if G.has_node(mandate_node_id):
            G.add_edge(mandate_node_id, map_node_id, relation="PRODUCES")

        # Link MAP to relevant clause series
        ref = map_obj.regulatory_reference or ""
        clause_series = _extract_clause_series(ref)
        if clause_series and G.has_node(clause_series):
            G.add_edge(map_node_id, clause_series, relation="REFERENCES")

    print(
        f"[Knowledge Graph] Built graph: "
        f"{G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges."
    )
    return G


def _prepopulate_canara_bank_series(G: nx.DiGraph) -> nx.DiGraph:
    """
    Pre-populates the graph with Canara Bank's key
    regulatory series based on documented penalty history.
    Used for demo — shows graph impact even before
    live scraping populates real data.
    """
    # ── KYC / CKYCR Series ──
    G.add_node("MD:KYC-MASTER-DIRECTION",
               type="MASTER_DIRECTION",
               title="Master Direction on KYC",
               regulator="RBI",
               series="KYC")
    G.add_node("CLAUSE:KYC-CKYCR-UPLOAD",
               type="CLAUSE",
               description="CKYCR Upload Requirements",
               series="KYC")
    G.add_node("CLAUSE:KYC-INOPERATIVE",
               type="CLAUSE",
               description="Inoperative Account KYC",
               series="KYC")
    G.add_edge("MD:KYC-MASTER-DIRECTION",
               "CLAUSE:KYC-CKYCR-UPLOAD",
               relation="CONTAINS")
    G.add_edge("MD:KYC-MASTER-DIRECTION",
               "CLAUSE:KYC-INOPERATIVE",
               relation="CONTAINS")

    # ── Priority Sector Lending Series ──
    G.add_node("MD:PSL-MASTER-DIRECTION",
               type="MASTER_DIRECTION",
               title="Master Direction on Priority Sector Lending",
               regulator="RBI",
               series="PSL")
    G.add_node("CLAUSE:PSL-TARGET-40",
               type="CLAUSE",
               description="40% ANBC Target",
               series="PSL")
    G.add_node("CLAUSE:PSL-BSBDA",
               type="CLAUSE",
               description="BSBDA Access Requirements",
               series="PSL")
    G.add_edge("MD:PSL-MASTER-DIRECTION",
               "CLAUSE:PSL-TARGET-40",
               relation="CONTAINS")
    G.add_edge("MD:PSL-MASTER-DIRECTION",
               "CLAUSE:PSL-BSBDA",
               relation="CONTAINS")

    # ── AML / PMLA Series ──
    G.add_node("MD:AML-PMLA-DIRECTION",
               type="MASTER_DIRECTION",
               title="AML/PMLA Reporting Directions",
               regulator="FIU_IND",
               series="AML")
    G.add_node("CLAUSE:AML-STR-REPORTING",
               type="CLAUSE",
               description="Suspicious Transaction Reporting",
               series="AML")
    G.add_node("CLAUSE:AML-CTR-REPORTING",
               type="CLAUSE",
               description="Cash Transaction Reporting",
               series="AML")
    G.add_edge("MD:AML-PMLA-DIRECTION",
               "CLAUSE:AML-STR-REPORTING",
               relation="CONTAINS")
    G.add_edge("MD:AML-PMLA-DIRECTION",
               "CLAUSE:AML-CTR-REPORTING",
               relation="CONTAINS")

    # ── Credit Information Series ──
    G.add_node("MD:CIC-DIRECTION",
               type="MASTER_DIRECTION",
               title="Credit Information Companies Directions",
               regulator="RBI",
               series="CIC")
    G.add_node("CLAUSE:CIC-7DAY-RECTIFICATION",
               type="CLAUSE",
               description="7-Day Rejection Rectification",
               series="CIC")
    G.add_edge("MD:CIC-DIRECTION",
               "CLAUSE:CIC-7DAY-RECTIFICATION",
               relation="CONTAINS")

    # ── CRR/SLR Series ──
    G.add_node("MD:CRR-SLR-DIRECTION",
               type="MASTER_DIRECTION",
               title="Cash Reserve Ratio and SLR Directions",
               regulator="RBI",
               series="CRR_SLR")
    G.add_node("CLAUSE:CRR-MAINTENANCE",
               type="CLAUSE",
               description="CRR Maintenance Requirements",
               series="CRR_SLR")
    G.add_edge("MD:CRR-SLR-DIRECTION",
               "CLAUSE:CRR-MAINTENANCE",
               relation="CONTAINS")

    return G


# ============================================================
# ADD MANDATE TO GRAPH
# ============================================================

def add_mandate_to_graph(
    G:       nx.DiGraph,
    mandate,
) -> nx.DiGraph:
    """
    Adds a single mandate node to the graph and
    creates edges to related clauses and series.

    Args:
        G:       Existing graph
        mandate: SQLAlchemy Mandate object

    Returns:
        Updated graph
    """
    mandate_id      = str(mandate.id)
    node_id         = f"MANDATE:{mandate_id[:8]}"
    signal_type     = mandate.signal_type or "UNKNOWN"

    G.add_node(
        node_id,
        type        = "MANDATE",
        mandate_id  = mandate_id,
        title       = (mandate.title or "")[:100],
        source      = mandate.source or "RBI",
        signal_type = signal_type,
        date_issued = str(mandate.date_issued) if mandate.date_issued else None,
    )

    # Create edges based on signal type
    if signal_type == "CIRCULAR_AMENDMENT":
        # Link to the series it amends
        series_node = _find_series_node(G, mandate.title or "")
        if series_node:
            G.add_edge(node_id, series_node, relation="AMENDS")

    elif signal_type in ("MANDATORY_IMMEDIATE", "MANDATORY_FUTURE"):
        # Link to relevant clause series
        series_node = _find_series_node(G, mandate.title or "")
        if series_node:
            G.add_edge(node_id, series_node, relation="CITES")

    return G


def _find_series_node(G: nx.DiGraph, title: str) -> Optional[str]:
    """
    Finds the most relevant master direction node
    based on keywords in the mandate title.
    """
    title_lower = title.lower()

    series_map = {
        "kyc":              "MD:KYC-MASTER-DIRECTION",
        "ckycr":            "MD:KYC-MASTER-DIRECTION",
        "inoperative":      "MD:KYC-MASTER-DIRECTION",
        "priority sector":  "MD:PSL-MASTER-DIRECTION",
        "bsbda":            "MD:PSL-MASTER-DIRECTION",
        "aml":              "MD:AML-PMLA-DIRECTION",
        "pmla":             "MD:AML-PMLA-DIRECTION",
        "money laundering": "MD:AML-PMLA-DIRECTION",
        "credit information": "MD:CIC-DIRECTION",
        "crr":              "MD:CRR-SLR-DIRECTION",
        "slr":              "MD:CRR-SLR-DIRECTION",
        "cash reserve":     "MD:CRR-SLR-DIRECTION",
        "statutory liquidity": "MD:CRR-SLR-DIRECTION",
    }

    for keyword, node_id in series_map.items():
        if keyword in title_lower and G.has_node(node_id):
            return node_id

    return None


def _extract_clause_series(ref_number: str) -> Optional[str]:
    """
    Maps a regulatory reference to a known clause node.
    """
    if not ref_number:
        return None

    ref_lower = ref_number.lower()

    clause_map = {
        "ckycr":       "CLAUSE:KYC-CKYCR-UPLOAD",
        "inoperative": "CLAUSE:KYC-INOPERATIVE",
        "priority":    "CLAUSE:PSL-TARGET-40",
        "bsbda":       "CLAUSE:PSL-BSBDA",
        "str":         "CLAUSE:AML-STR-REPORTING",
        "ctr":         "CLAUSE:AML-CTR-REPORTING",
        "cic":         "CLAUSE:CIC-7DAY-RECTIFICATION",
        "crr":         "CLAUSE:CRR-MAINTENANCE",
    }

    for keyword, clause_node in clause_map.items():
        if keyword in ref_lower:
            return clause_node

    return None


# ============================================================
# FIND AFFECTED MAPs
# ============================================================

def find_affected_maps(
    G:          nx.DiGraph,
    ref_number: str,
    db:         Session,
) -> list[dict]:
    """
    When a new amendment arrives, finds all existing MAPs
    that reference the same regulatory clause series.

    This is the core knowledge graph intelligence feature.
    A MAJOR amendment to KYC instantly shows all KYC MAPs
    that may need to be re-evaluated.

    Args:
        G:          The regulatory graph
        ref_number: Reference number of the new mandate
        db:         SQLAlchemy session

    Returns:
        List of affected MAP dicts with id, obligation, priority
    """
    from backend.models import Map

    # Find the series this amendment belongs to
    affected_map_ids = set()

    # Check which clause/series nodes this ref_number connects to
    for node_id, node_data in G.nodes(data=True):
        if node_data.get("type") == "MANDATE":
            continue

        # Check if the ref_number relates to this node's series
        series = node_data.get("series", "")
        if _ref_matches_series(ref_number, series):
            # Find all MAP nodes referencing this clause
            for predecessor in G.predecessors(node_id):
                pred_data = G.nodes[predecessor]
                if pred_data.get("type") == "MAP":
                    map_id = pred_data.get("map_id")
                    if map_id:
                        affected_map_ids.add(map_id)

    if not affected_map_ids:
        return []

    # Fetch full MAP details from database
    from uuid import UUID
    affected_maps = []

    for map_id_str in affected_map_ids:
        try:
            map_obj = db.query(Map).filter(
                Map.id == UUID(map_id_str)
            ).first()
            if map_obj:
                affected_maps.append({
                    "map_id":         str(map_obj.id),
                    "obligation_text": map_obj.obligation_text,
                    "priority_tier":  map_obj.priority_tier,
                    "mpi_score":      float(map_obj.mpi_score or 0),
                    "status":         map_obj.status,
                    "impact":         "POTENTIALLY_AFFECTED",
                    "reason": (
                        "This MAP references the same regulatory "
                        "clause series as the new amendment."
                    )
                })
        except Exception:
            continue

    print(
        f"[Knowledge Graph] Found {len(affected_maps)} "
        f"MAPs potentially affected by amendment."
    )
    return affected_maps


def _ref_matches_series(ref_number: str, series: str) -> bool:
    """
    Checks if a reference number belongs to a regulatory series.
    """
    if not ref_number or not series:
        return False

    ref_lower    = ref_number.lower()
    series_lower = series.lower()

    series_keywords = {
        "kyc":     ["kyc", "ckycr", "aml", "dor.aml"],
        "psl":     ["priority", "psl", "dor.ret"],
        "aml":     ["aml", "pmla", "fiu", "money laundering"],
        "cic":     ["cic", "credit information", "cibil"],
        "crr_slr": ["crr", "slr", "cash reserve", "dor.ret.rec"],
    }

    keywords = series_keywords.get(series_lower, [series_lower])
    return any(kw in ref_lower for kw in keywords)


# ============================================================
# GET MANDATE LINEAGE
# ============================================================

def get_mandate_lineage(
    G:           nx.DiGraph,
    mandate_id:  str,
) -> list[dict]:
    """
    Returns the chain of amendments for a given mandate.
    Shows the history of how a regulation evolved.

    Args:
        G:           The regulatory graph
        mandate_id:  UUID string of the mandate

    Returns:
        List of related mandate nodes in chronological order
    """
    node_id = f"MANDATE:{mandate_id[:8]}"

    if not G.has_node(node_id):
        return []

    lineage = []

    # Walk the AMENDS edges to find the chain
    visited = set()
    queue   = [node_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        node_data = G.nodes[current]
        if node_data.get("type") == "MANDATE":
            lineage.append({
                "node_id":    current,
                "mandate_id": node_data.get("mandate_id"),
                "title":      node_data.get("title"),
                "date":       node_data.get("date_issued"),
                "signal":     node_data.get("signal_type"),
            })

        # Follow AMENDS edges
        for neighbor in G.successors(current):
            edge_data = G.edges[current, neighbor]
            if edge_data.get("relation") == "AMENDS":
                queue.append(neighbor)

    return lineage


# ============================================================
# GRAPH STATS
# ============================================================

def get_graph_stats(G: nx.DiGraph) -> dict:
    """
    Returns summary statistics about the knowledge graph.
    Displayed on the dashboard.
    """
    node_types = {}
    for _, data in G.nodes(data=True):
        t = data.get("type", "UNKNOWN")
        node_types[t] = node_types.get(t, 0) + 1

    edge_types = {}
    for _, _, data in G.edges(data=True):
        r = data.get("relation", "UNKNOWN")
        edge_types[r] = edge_types.get(r, 0) + 1

    return {
        "total_nodes":  G.number_of_nodes(),
        "total_edges":  G.number_of_edges(),
        "node_types":   node_types,
        "edge_types":   edge_types,
    }


# ============================================================
# STANDALONE TEST
# Run: python -m backend.graph.regulatory_graph
# ============================================================

if __name__ == "__main__":
    print("Testing Regulatory Knowledge Graph (no DB needed)...\n")

    G = nx.DiGraph()
    G = _prepopulate_canara_bank_series(G)

    stats = get_graph_stats(G)
    print(f"Graph Stats:")
    print(f"  Nodes : {stats['total_nodes']}")
    print(f"  Edges : {stats['total_edges']}")
    print(f"  Types : {stats['node_types']}")

    print(f"\nNodes in graph:")
    for node, data in G.nodes(data=True):
        print(f"  {node} ({data.get('type')})")

    print(f"\nEdges in graph:")
    for src, dst, data in G.edges(data=True):
        print(f"  {src} --[{data.get('relation')}]--> {dst}")

    # Test series matching
    test_refs = [
        "RBI/2026-2027/001DOR.AML.REC.01/14.01.001/2026-27",
        "RBI/2026-2027/106DOR.RET.REC.88/12.01.001/2026-27",
    ]

    print(f"\nSeries matching test:")
    for ref in test_refs:
        node = _find_series_node(G, ref)
        print(f"  {ref[:40]}... → {node}")