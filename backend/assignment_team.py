"""Team membership with compatibility for single-officer assignments."""

def member_ids(record, legacy="officer_id"):
    plural = "petugas_ids" if legacy == "petugas_id" else "officer_ids"
    return list(dict.fromkeys(record.get(plural) or ([record[legacy]] if record.get(legacy) else [])))


def member_query(query, user_id, legacy="officer_id"):
    plural = "petugas_ids" if legacy == "petugas_id" else "officer_ids"
    return {**query, "$and": [*query.get("$and", []), {"$or": [{legacy: user_id}, {plural: user_id}]}]}
