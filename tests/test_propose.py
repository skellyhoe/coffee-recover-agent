from recovery.propose import propose_mappings

KNOWN = {"K1": "Known One", "K2": "Known Two"}
CATALOG = {"Known One": "P1", "Known Two": "P2", "New A": "P3", "New B": "P4", "New C": "P5"}


def order(oid, *cups, day="2026-09-01"):
    return {"id": oid, "date": day, "time": "09:00", "paid": sum(p for _, p in cups),
            "cups": [{"code": c, "price": p} for c, p in cups]}


def rows(oid, *cups):
    return [{"order_id": oid, "product_name": n, "price": p} for n, p in cups]


def run(orders, export, mapping=KNOWN):
    result = propose_mappings(orders, export, mapping, CATALOG)
    return {p["code"]: p for p in result["proposals"]}, result


def test_price_pairing_after_removing_known_cups():
    p, _ = run([order("O1", ("K1", 300), ("U1", 350))],
               rows("O1", ("Known One", 300), ("New A", 350)))
    assert p["U1"]["product_name"] == "New A"
    assert p["U1"]["methods"] == {"price": 1}
    assert p["U1"]["in_catalog"]


def test_known_cup_at_same_price_does_not_confuse_pairing():
    p, _ = run([order("O1", ("K1", 350), ("U1", 350))],
               rows("O1", ("Known One", 350), ("New A", 350)))
    assert p["U1"]["product_name"] == "New A"


def test_elimination_unlocks_same_price_pair():
    orders = [order("O1", ("U1", 350)), order("O2", ("U1", 350), ("U2", 350))]
    export = rows("O1", ("New A", 350)) + rows("O2", ("New A", 350), ("New B", 350))
    p, result = run(orders, export)
    assert p["U1"]["product_name"] == "New A"
    assert p["U2"]["product_name"] == "New B"
    assert p["U2"]["methods"] == {"elimination": 1}
    assert not result["ambiguous_orders"]


def test_inseparable_codes_get_no_candidate():
    p, result = run([order("O1", ("U1", 350), ("U2", 350))],
                    rows("O1", ("New A", 350), ("New B", 350)))
    assert p["U1"]["product_name"] is None and p["U2"]["product_name"] is None
    assert result["ambiguous_orders"] == {"O1": ["U1", "U2"]}


def test_code_with_two_names_is_a_conflict():
    p, _ = run([order("O1", ("U1", 350)), order("O2", ("U1", 350))],
               rows("O1", ("New A", 350)) + rows("O2", ("New B", 350)))
    assert p["U1"]["product_name"] is None
    assert p["U1"]["conflicts"]
    assert p["U1"]["candidate_names"] == {"New A": 1, "New B": 1}


def test_two_codes_claiming_one_name_conflict():
    p, _ = run([order("O1", ("U1", 350)), order("O2", ("U2", 350))],
               rows("O1", ("New A", 350)) + rows("O2", ("New A", 350)))
    assert p["U1"]["conflicts"] and p["U2"]["conflicts"]


def test_name_already_mapped_conflict():
    p, _ = run([order("O1", ("U1", 300))], rows("O1", ("Known One", 300)))
    assert any("already mapped" in c for c in p["U1"]["conflicts"])


def test_provisional_code_contradicted_later_is_banned_and_taints_nothing():
    # U1 pairs with New A in O1, but O2 has U1 and the only same-price rows lack New A.
    orders = [order("O1", ("U1", 350)), order("O2", ("U1", 350), ("U2", 350))]
    export = rows("O1", ("New A", 350)) + rows("O2", ("New B", 350), ("New C", 350))
    p, _ = run(orders, export)
    assert p["U1"]["conflicts"]
    assert p["U2"]["product_name"] is None


def test_price_disagreement_is_counted():
    p, _ = run([order("O1", ("U1", 350))], rows("O1", ("New A", 340)))
    assert p["U1"]["product_name"] == "New A"
    assert p["U1"]["price_mismatches"] == 1


def test_order_missing_from_export_is_reported_not_guessed():
    p, result = run([order("O1", ("U1", 350))], [])
    assert result["orders_missing_from_export"] == ["O1"]
    assert p["U1"]["product_name"] is None and p["U1"]["total_cups_seen"] == 1


def test_contradiction_of_existing_mapping_reported():
    _, result = run([order("O1", ("K1", 300))], rows("O1", ("Known Two", 300)))
    assert result["existing_mapping_contradictions"][0]["code"] == "K1"


def test_multiple_cups_counted():
    p, _ = run([order("O1", ("U1", 350), ("U1", 350)), order("O2", ("U1", 350))],
               rows("O1", ("New A", 350), ("New A", 350)) + rows("O2", ("New A", 350)))
    assert p["U1"]["cups"] == 3 and p["U1"]["orders"] == 2
