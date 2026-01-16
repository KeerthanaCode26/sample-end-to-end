from __future__ import annotations
from core.dbdata import db_collection
from core.oradata import oradata_query
from core.oradata import oradata_anon_block

from pydantic import BaseModel


from typing import Any, Dict, List
from datetime import datetime, timedelta

from pymongo import ASCENDING, UpdateOne

from config.app import uvicornLogger
from core.dbdata import db_collection

class CourseCacheEntry:
    def __init__(self) -> None:
        self.data: List[Dict[str, Any]] = []
        self.cache_timestamp: float = 0.0 

    def is_expired(self, hours: int = 2) -> bool:
        #Return True if the cache is older than `hours` hours.
        return (datetime.now() - timedelta(hours=hours)).timestamp() > self.cache_timestamp


# In-memory cache keyed by term_code(follows sec auth tool pattern for cache)
_course_cache: Dict[str, CourseCacheEntry] = {}


UNIQUE_KEYS = ["term_code", "college_code", "trans_subj", "trans_numb"]

def _normalize_oracle_row(row: Dict[str, Any]) -> Dict[str, Any]:
    inst_numb = row.get("INST_NUMB")
    return {
        "term_code":    row.get("TERM_CODE"),
        "college_code": row.get("COLLEGE_CODE"),
        "college_name": row.get("COLLEGE_NAME"),
        "trans_subj":   row.get("TRANS_SUBJ"),
        "trans_numb":   row.get("TRANS_NUMB"),
        "inst_subj":    row.get("INST_SUBJ"),
        "inst_numb":    inst_numb,
        "standard": "Lower" if inst_numb == "1910" else "Higher",
        "status":  "RF",
        "filename": None,
        "fsid":     None,
    }


    # Create the unique index once (idempotent)
def _ensure_unique_index():
    col = db_collection("course")
    try:
        col.create_index(
            [(k, ASCENDING) for k in UNIQUE_KEYS],
            name="uq_course_key",
            unique=True,
            background=True,
        )
    except Exception as e:
        # Likely already exists or racing; not fatal.
        uvicornLogger.warning(f"course unique index creation: {e}")

def _insert_new_courses_from_oracle(term_code: str) -> None:

    rows: List[Dict[str, Any]] = course_query(term_code) or []
    if not rows:
        return

    col = db_collection("course")
    now = datetime.utcnow()
    ops: List[UpdateOne] = []

    for r in rows:
        doc = _normalize_oracle_row(r)
        # skip if identity incomplete
        if not all(doc.get(k) for k in UNIQUE_KEYS):
            continue

        key = {k: doc[k] for k in UNIQUE_KEYS}
        ops.append(
            UpdateOne(
                key,
                {"$setOnInsert": {**doc, "created_at": now, "updated_at": now}},
                upsert=True,
            )
        )

    if ops:
        try:
            col.bulk_write(ops, ordered=False)
        except Exception as e:
            uvicornLogger.exception(e)

# getting term code for caching
def _load_term_from_mongo(term_code: str) -> List[Dict[str, Any]]:
    col = db_collection("course")
    docs = list(
        col.find({"term_code": term_code}, {})
           .sort([("college_code", ASCENDING), ("trans_subj", ASCENDING), ("trans_numb", ASCENDING)])
    )
    for d in docs:
        _id = d.get("_id")
        if _id is not None:
            d["_id"] = str(_id)
    return docs

# Main function to refresh and cache term 
#     Refresh pipeline for a term:
#       1) Insert-only upsert from Oracle into Mongo
#       2) Read from Mongo
#       3) Cache in memory

def _refresh_and_cache_term(term_code: str) -> List[Dict[str, Any]]:

    _ensure_unique_index()
    _insert_new_courses_from_oracle(term_code)
    docs = _load_term_from_mongo(term_code)

    entry = _course_cache.get(term_code) or CourseCacheEntry()
    entry.data = docs
    entry.cache_timestamp = datetime.now().timestamp()
    _course_cache[term_code] = entry

    return docs

# Public API for router/service:
#   - If cache is missing/stale -> refresh
#   - Return cached data
def list_courses_for_term(term_code: str, ttl_hours: int = 2) -> List[Dict[str, Any]]:

    entry = _course_cache.get(term_code)
    if entry is None or entry.is_expired(hours=ttl_hours):
        return _refresh_and_cache_term(term_code)
    return entry.data

#To do: see if activity date is creating issue
def course_query(term_code : str) :
    query = """
    SELECT DISTINCT
    ....
    """
    results, error = oradata_query(query, {'term_code' : term_code})
    if error is not None :
        raise Exception(error)
    
    return results
    
    
#helper function to query oracle database
def oradata_query(query, bind_args, params = oradata_connection_parameters) :

    results = []
    error = None

    try :
        with oracledb.connect(params=params) as connection :
            connection.autocommit = False 
            with connection.cursor() as cursor:
                cursor.execute(query, bind_args)
                
                # cursor.description will also help identify when an "implied" cursor is used - since straight up select queries return a description, which is used to identify columns and build dicts
                results_sets = ([cursor], cursor.getimplicitresults())[cursor.description is None]

                for indx, result_set in enumerate(results_sets) :
                    #build dictionary keys
                    columns = [col[0] for col in result_set.description]
                    result_set.rowfactory = lambda *args: dict(zip(columns, args))

                    for row in result_set:
                        results.append(row)
            connection.rollback() # just incase someone sends an insert/update statement

    except (oracledb.Error, oracledb.NotSupportedError) as e :
        error_obj, = e.args
        error = {'status' : 'error', 'message' : error_obj.message}
        print(error_obj)
    return results, error