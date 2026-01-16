from typing import Any, Dict, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status
from starlette.authentication import requires
from pymongo import UpdateOne, ASCENDING

from models.returnset import ReturnSetModel
from models.course import CourseModel, AssignEvaluatorsPayload
from config.app import uvicornLogger
from core.dbdata import db_collection
from core.uvicorn_logger import UvicornLogger
from data import course, department
from pydantic import BaseModel, Field
import re

router = APIRouter(tags=["course"])
class RequestsSearchFilter(BaseModel) :
    search : str = Field('', max_length=6)

from bson import ObjectId


@router.post("/course", response_model=ReturnSetModel)
def display_course(request: Request, term_code: str, searchFilter : RequestsSearchFilter):

    if not any(role in ["******.Admin"] for role in request.user.roles):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Error: Unauthorized Access")

    try:
        # _doc is to update/refresh the mongo
        _docs = course.list_courses_for_term(term_code, ttl_hours=2)
        # get courses from mongo with status 'RF' or 'RT'
        search_args = (searchFilter.search or '').strip()
        query: Dict[str, Any] = {
            "term_code": term_code,
            "status": {"$in": ["RF", "RT"]}
        }
        if search_args:
            query["college_code"] = {"$regex": f"^{re.escape(search_args)}"}

        col = db_collection("course")
        cursor = col.find(query)
        docs = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            docs.append(doc)
        return ReturnSetModel(status="success", data=docs)

    except Exception as e:
        uvicornLogger.exception(e)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class CourseDetailsPayload(BaseModel):
    trans_subj: str
    id: str

@router.post("********/details", response_model=ReturnSetModel)
async def get_course_details(request: Request, term_code: str, body: CourseDetailsPayload):
    if not any(role in ["******.Admin"] for role in request.user.roles):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Error: Unauthorized Access")

    try:
        id = body.id
        trans_subj = body.trans_subj

        course_col = db_collection("course")
        course = course_col.find_one({"_id": ObjectId(id)})

        # If course already has evaluator info, ensure evaluators_names exists and return it
        if course and course.get('assigned_evaluator'):
            # Get names for the evaluators list
            evaluator_ids = course.get('evaluators', []) or []
            names = department.get_evaluator_name(evaluator_ids) or []

            # If not stored yet, persist evaluators_names to Mongo
            if course.get('evaluators_names') != names:
                course_col.update_one(
                    {"_id": ObjectId(id)},
                    {"$set": {"evaluators_names": names}}
                )

            return ReturnSetModel(
                status="success",
                data={
                    "assigned_evaluator": course.get('assigned_evaluator'),
                    "assigned_coll_code": course.get('assigned_coll_code'),
                    "assigned_coll_desc": course.get('assigned_coll_desc'),
                    "assigned_dept_code": course.get('assigned_dept_code'),
                    "assigned_dept_desc": course.get('assigned_dept_desc'),
                    "evaluators": evaluator_ids,
                    "evaluators_names": names,
                }
            )

        # Else, get evaluator info from department config
        col = db_collection("departmentconfig")
        dept_config = col.find_one(
            {"transfer_course": trans_subj},
            {
                "_id": 0,
                "evaluator": 1,
                "coll_code": 1,
                "coll_desc": 1,
                "dept_code": 1,
                "dept_desc": 1
            }
        )

        if not dept_config or 'evaluator' not in dept_config:
            return ReturnSetModel(
                status="success",
                data={
                    "assigned_evaluator": None,
                    "assigned_coll_code": None,
                    "assigned_coll_desc": None,
                    "assigned_dept_code": None,
                    "assigned_dept_desc": None,
                    "evaluators": [],
                    "evaluators_names": [], 
                }
            )

        evaluator_ids = dept_config['evaluator'] or []
        if not isinstance(evaluator_ids, list) or len(evaluator_ids) == 0:
            return ReturnSetModel(
                status="success",
                data={
                    "assigned_evaluator": None,
                    "assigned_coll_code": None,
                    "assigned_coll_desc": None,
                    "assigned_dept_code": None,
                    "assigned_dept_desc": None,
                    "evaluators": [],
                    "evaluators_names": [],
                }
            )

        primary_evaluator = evaluator_ids[0]
        evaluators = department.dept_for_evaluator(primary_evaluator) or []
        if evaluators:
            names = department.get_evaluator_name(evaluator_ids) or []
            info = evaluators[0]
            update_fields = {
                "evaluators": evaluator_ids,
                "evaluators_names": names,                 
                "assigned_evaluator": primary_evaluator,
                "assigned_coll_code": info.get("coll_code"),
                "assigned_coll_desc": info.get("coll_desc"),
                "assigned_dept_code": info.get("dept_code"),
                "assigned_dept_desc": info.get("dept_desc"),
            }
            course_col.update_one({"_id": ObjectId(id)}, {"$set": update_fields})

            return ReturnSetModel(
                status="success",
                data={
                    "assigned_evaluator": primary_evaluator,
                    "assigned_coll_code": info.get("coll_code"),
                    "assigned_coll_desc": info.get("coll_desc"),
                    "assigned_dept_code": info.get("dept_code"),
                    "assigned_dept_desc": info.get("dept_desc"),
                    "evaluators": evaluator_ids,
                    "evaluators_names": names,                 
                }
            )

        # Fallback: no resolvable evaluator info
        return ReturnSetModel(
            status="success",
            data={
                "assigned_evaluator": None,
                "assigned_coll_code": None,
                "assigned_coll_desc": None,
                "assigned_dept_code": None,
                "assigned_dept_desc": None,
                "evaluators": [],
                "evaluators_names": [],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        uvicornLogger.exception(e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding department configuration: {str(e)}"
        )



@router.patch("***/send", response_model=ReturnSetModel)
def assign_evaluators_to_course(request: Request, body: AssignEvaluatorsPayload):
    if not any(role in ["******.Admin"] for role in request.user.roles):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Error: Unauthorized Access")

    # First, check if the course already has evaluator information
    course_col = db_collection("course")
    course_id = ObjectId(body.course_id)
    
    # Get the current course data
    course = course_col.find_one({"_id": course_id})
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # If course already has evaluators, just update the status
    if course.get('evaluators') and course.get('assigned_evaluator'):
        update_doc = {
            "$set": {
                "updated_at": datetime.utcnow(),
                "status": "SE"
            }
        }
        
        res = course_col.update_one({"_id": course_id}, update_doc)
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Course not found")
            
        return ReturnSetModel(
            status="success",
            data={"matched_count": res.matched_count}
        )
    
    # Fall back to department config if no evaluators exist
    try:
        col = db_collection("departmentconfig")
        dept_config = col.find_one(
            {"transfer_course": body.trans_subj},
            {
                "_id": 0,
                "evaluator": 1,
                "coll_code": 1,
                "coll_desc": 1,
                "dept_code": 1,
                "dept_desc": 1
            }
        )
        
        if not dept_config:
            raise HTTPException(
                status_code=404,
                detail=f"No department configuration found for subject: {body.trans_subj}. Please add in Department Config"
            )
            
        # Get all evaluators for the subject
        evaluators = dept_config.get("evaluator", [])
        if not evaluators:
            raise HTTPException(
                status_code=404,
                detail=f"No evaluators found for subject: {body.trans_subj}"
            )
        names = department.get_evaluator_name(evaluators) or []
        # Convert to list if not already and ensure all are strings
        matched = [str(e) for e in (evaluators if isinstance(evaluators, list) else [evaluators])]
        
        # Use the first evaluator as primary for assignment
        primary = matched[0] if matched else None
        
        # Set assigned fields from department config
        assigned_fields = {
            "assigned_evaluator": primary,
            "assigned_coll_code": dept_config.get("coll_code"),
            "assigned_coll_desc": dept_config.get("coll_desc"),
            "assigned_dept_code": dept_config.get("dept_code"),
            "assigned_dept_desc": dept_config.get("dept_desc"),
            "status": "SE",
            "evaluators_names": names,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        uvicornLogger.exception(e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding department configuration: {str(e)}"
        )

    # 3) Update the specific course using its _id
    col = db_collection("course")
    try:
        course_id = ObjectId(body.course_id)
    except:
        raise HTTPException(
            status_code=400,
            detail="Invalid course ID format"
        )
        
    query = {
        "_id": course_id
    }

    try:
        # Update evaluators list and assigned fields in a single operation
        update_doc = {
            "$set": {
                "updated_at": datetime.utcnow(),
                "evaluators": matched,
                **assigned_fields
            }
        }

        res = col.update_one(query, update_doc, upsert=False)

        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Course not found")

        return ReturnSetModel(status="success", data={"evaluators": matched, **assigned_fields})
    except HTTPException:
        raise
    except Exception as e:
        uvicornLogger.exception(e)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.post("/manualcourse", response_model=ReturnSetModel)
async def create_manual_course(request: Request, course_data: CourseModel):
    if not any(role in ['******.Admin'] for role in request.user.roles):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Admin access required"
        )

    try:
        col = db_collection('course')

        # Create a copy of the model data and update with normalized values
        course_dict = course_data.model_dump()
        
        # Normalize fields used for uniqueness (prevents case/whitespace dupes)
        normalized_data = {
            "term_code": (course_dict.get("term_code") or "").strip(),
            "college_code": (course_dict.get("college_code") or "").strip(),
            "college_name": (course_dict.get("college_name") or "").strip(),
            "trans_subj": (course_dict.get("trans_subj") or "").strip().upper(),
            "trans_numb": (course_dict.get("trans_numb") or "").strip(),
            "inst_subj": (course_dict.get("inst_subj") or "").strip().upper(),
            "inst_numb": (course_dict.get("inst_numb") or "").strip(),
            "standard": "Lower" if (course_dict.get("inst_numb") or "").strip() == "1910" else "Higher",
            "status": "RF", 
            "source": "manual",
            "fsid": None,
            "filename": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Duplicate check using the normalized key
        key = {
            "term_code": normalized_data["term_code"],
            "college_code": normalized_data["college_code"],
            "trans_subj": normalized_data["trans_subj"],
            "trans_numb": normalized_data["trans_numb"],
        }
        if col.find_one(key):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="A manual course with these details already exists"
            )

        result = col.insert_one(normalized_data)

        # Return the inserted doc (serialize _id)
        new_course = col.find_one({"_id": result.inserted_id}, {"_id": 0})
        return ReturnSetModel(status="success", data=new_course)

    except HTTPException:
        raise
    except Exception as e:
        UvicornLogger().exception(f"Error creating manual course: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating course: {str(e)}"
        )

class EvaluatorUpdate(BaseModel):
    id: str
    evaluator_id: str

@router.patch("***/update_evaluator", response_model=ReturnSetModel)
async def update_evaluator(request: Request, payload: EvaluatorUpdate):
    if not any(role in ['******.Admin'] for role in request.user.roles):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Unauthorized: Admin access required")
    
    try:
        course_id = payload.id
        new_evaluator_id = payload.evaluator_id
        
        course_collection = db_collection("course")
        course = course_collection.find_one({"_id": ObjectId(course_id)})
        
        # Get evaluators for the department
        evaluators = department.dept_for_evaluator(new_evaluator_id)
        
        if not evaluators:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND,detail=f"No evaluators found for department {course.get('dept_code')}")
        
        # Update course with new evaluator information
        update_fields = {
            "evaluators": [new_evaluator_id],
            "evaluators_names": department.get_evaluator_name([new_evaluator_id]),
            "assigned_evaluator": new_evaluator_id,
            "assigned_coll_code": evaluators[0].get("coll_code"),
            "assigned_coll_desc": evaluators[0].get("coll_desc"),
            "assigned_dept_code": evaluators[0].get("dept_code"),
            "assigned_dept_desc": evaluators[0].get("dept_desc"),
        }
        
        # Update the course in the database
        result = course_collection.update_one(
            {"_id": ObjectId(course_id)},
            {"$set": update_fields}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to update course with new evaluator information")
            
        # Get the updated course
        updated_course = course_collection.find_one({"_id": ObjectId(course_id)})
        updated_course['_id'] = str(updated_course['_id'])
        
        return ReturnSetModel(status='success', data=updated_course)
        
    except HTTPException:
        raise
    except Exception as e:
        uvicornLogger.exception(f"Error updating evaluator: {str(e)}")
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Error updating evaluator: {str(e)}")