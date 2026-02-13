"""
Synthetic Data Router
Endpoints for schema extraction and data generation
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from db import get_db
from models import Schema, SyntheticRun, SyntheticData
from routers.chats import ensure_chat_and_append_user_message, append_agent_message
from services.synthetic.ui_schema.extractor import UISchemaExtractor
from services.synthetic.api_schema.extractor import APISchemaExtractor
from services.synthetic.unified_schema.merger import SchemaMerger
from services.synthetic.sdv_engine.generator import SDVGenerator
from agents.synthetic_data.graph import run_synthetic_data_workflow
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ========== REQUEST MODELS ==========

class UISchemaRequest(BaseModel):
    html_content: Optional[str] = None
    url: Optional[str] = None
    fields_structure: Optional[Dict[str, Any]] = None

class APISchemaRequest(BaseModel):
    openapi_spec: Optional[Dict[str, Any]] = None
    sample_response: Optional[Dict[str, Any]] = None
    endpoint: str

class MergeSchemaRequest(BaseModel):
    ui_schema_id: Optional[int] = None
    api_schema_id: Optional[int] = None
    ui_schema: Optional[Dict[str, Any]] = None
    api_schema: Optional[Dict[str, Any]] = None

class GenerateDataRequest(BaseModel):
    model_config = {"populate_by_name": True}
    schema_id: Optional[int] = None
    schema: Optional[Dict[str, Any]] = None
    num_rows: int = 10
    model_name: str = Field(default="GaussianCopula", alias="model")

class NaturalLanguageRequest(BaseModel):
    model_config = {"populate_by_name": True}
    user_input: str
    model_name: str = Field(default="GaussianCopula", alias="model")
    chat_id: Optional[int] = None  # If set, append to this chat and return chat_id in response

# ========== ENDPOINTS ==========

@router.post("/generate-from-text")
async def generate_from_natural_language(request: NaturalLanguageRequest, db: Session = Depends(get_db)):
    """
    Generate synthetic data from natural language description using LangGraph workflow
    This endpoint now uses the agent-based workflow with UI crawling
    """
    chat_id = None
    try:
        logger.info("="*80)
        logger.info("SYNTHETIC DATA REQUEST RECEIVED (LangGraph Workflow)")
        logger.info("User Input: %s...", request.user_input[:100] if len(request.user_input) > 100 else request.user_input)
        logger.info("Model: %s", request.model_name)
        logger.info("="*80)

        # Session/state: ensure chat exists and append user message
        chat_id = ensure_chat_and_append_user_message(
            db, request.chat_id, "synthetic", request.user_input
        )

        # Run LangGraph workflow (with progress-aware chat_id)
        result = await run_synthetic_data_workflow(
            test_case=request.user_input,
            num_rows=10,  # Default, can be parsed from user input
            db=db,
            chat_id=chat_id,
        )
        
        if result['status'] == 'success':
            logger.info("Workflow complete! Run ID: %s", result['run_id'])
            logger.info("="*80)
            agent_text = "Generated synthetic data run #%s with %s rows." % (
                result['run_id'], len(result['generated_data'])
            )
            payload = {
                "kind": "synthetic",
                "runId": result["run_id"],
                "schemaId": result.get("schema_id"),
                "rowsGenerated": len(result["generated_data"]),
                "dataPreview": (result["generated_data"] or [])[:50],
            }
            append_agent_message(db, chat_id, agent_text, payload)
            return {
                "message": "Synthetic data generated successfully via agent workflow",
                "run_id": result['run_id'],
                "schema_id": result['schema_id'],
                "rows_generated": len(result['generated_data']),
                "data": result['generated_data'],
                "chat_id": chat_id,
            }
        else:
            append_agent_message(
                db, chat_id,
                "Sorry, workflow failed: %s" % result.get("error", "Unknown error"),
                None,
            )
            raise HTTPException(status_code=500, detail=result.get('error', 'Workflow failed'))
        
    except Exception as e:
        logger.error("Synthetic workflow error: %s", str(e))
        if chat_id is not None:
            try:
                append_agent_message(db, chat_id, "Sorry, something went wrong: %s" % str(e), None)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-from-text-legacy")
async def generate_from_natural_language_legacy(request: NaturalLanguageRequest, db: Session = Depends(get_db)):
    """Generate synthetic data from natural language description (LEGACY - direct approach)"""
    try:
        logger.info("="*80)
        logger.info(f"🧬 SYNTHETIC DATA REQUEST RECEIVED (LEGACY)")
        logger.info(f"📝 User Input: {request.user_input[:100]}...")
        logger.info(f"🎲 Model: {request.model_name}")
        logger.info("="*80)
        
        # Parse user input to extract schema and num_rows
        from utils.azure_openai import get_openai_client
        import os
        import re
        
        logger.info("🤖 Initializing Azure OpenAI client...")
        client = get_openai_client()
        logger.info("✅ Azure OpenAI client initialized")
        
        # Use OpenAI to parse the request
        system_prompt = """You are a helpful assistant that converts natural language data requests into structured schemas.
        
        Extract:
        1. Number of rows to generate
        2. Field names and their types
        
        Return a JSON with this format:
        {
            "num_rows": <number>,
            "fields": {
                "field_name": {"type": "string|integer|float|datetime|boolean|email|phone|address|name", "required": true}
            }
        }
        
        Type mappings:
        - email, mail -> email
        - phone, mobile, tel -> phone
        - address, street, city -> address
        - name, first_name, last_name -> name
        - age, quantity, count, id, number -> integer
        - amount, price, salary, cost -> float
        - date, time, created, updated -> datetime
        - is_, has_, active, enabled -> boolean
        - anything else -> string
        """
        
        logger.info("Calling Azure OpenAI to parse schema...")
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_input}
            ],
            temperature=0
        )
        logger.info("✅ OpenAI response received")
        
        import json
        schema_data = json.loads(response.choices[0].message.content)
        logger.info(f"📊 Parsed schema data: {schema_data}")
        
        num_rows = schema_data.get('num_rows', 10)
        fields = schema_data.get('fields', {})
        
        logger.info(f"📋 Parsed schema: {len(fields)} fields, {num_rows} rows")
        
        # Build schema
        schema = {"fields": fields}
        
        # Save schema to database
        db_schema = Schema(source="natural_language", schema_json=schema)
        db.add(db_schema)
        db.commit()
        db.refresh(db_schema)
        
        logger.info(f"💾 Schema saved with ID: {db_schema.id}")
        
        # Generate synthetic data
        generator = SDVGenerator()
        logger.info(f"🎲 Generating {num_rows} rows using {request.model_name}...")
        
        synthetic_data = generator.generate(schema, num_rows=num_rows, model=request.model_name)
        
        logger.info(f"✅ Generated {len(synthetic_data)} rows")
        
        # Save run
        run = SyntheticRun(schema_id=db_schema.id, rows=num_rows, model=request.model_name)
        db.add(run)
        db.commit()
        db.refresh(run)

        # Save data
        for row in synthetic_data:
            data_row = SyntheticData(run_id=run.id, row_json=row)
            db.add(data_row)
        db.commit()

        logger.info(f"✅ Complete! Run ID: {run.id}")
        logger.info("="*80)
        logger.info(f"🎉 SUCCESS: Generated {len(synthetic_data)} rows")
        logger.info(f"📊 Run ID: {run.id} | Schema ID: {db_schema.id}")
        logger.info("="*80)
        
        return {
            "run_id": run.id,
            "schema_id": db_schema.id,
            "data": synthetic_data,
            "count": len(synthetic_data),
            "message": "Synthetic data generated successfully from natural language"
        }
        
    except Exception as e:
        logger.error("="*80)
        logger.error(f"❌ ERROR in natural language generation")
        logger.error(f"📝 Error: {str(e)}")
        logger.error("="*80)
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# ========== ENDPOINTS ==========

@router.post("/ui-schema")
async def extract_ui_schema(request: UISchemaRequest, db: Session = Depends(get_db)):
    """Extract schema from UI elements"""
    try:
        logger.info("🧬 Synthetic Data: Starting UI schema extraction...")
        
        extractor = UISchemaExtractor()
        
        if request.html_content:
            logger.info(f"📝 Extracting from HTML content ({len(request.html_content)} chars)...")
            schema = extractor.extract_from_html(request.html_content)
        elif request.url:
            logger.info(f"🌐 Extracting from URL: {request.url}")
            schema = extractor.extract_from_url(request.url)
        elif request.fields_structure:
            logger.info("📋 Extracting from fields structure...")
            schema = extractor.extract_from_structure(request.fields_structure)
        else:
            raise HTTPException(status_code=400, detail="Provide html_content, url, or fields_structure")
        
        logger.info(f"✅ Schema extracted: {schema.get('total_fields', 0)} fields found")
        
        # Save to database
        db_schema = Schema(source="ui", schema_json=schema)
        db.add(db_schema)
        db.commit()
        db.refresh(db_schema)
        
        logger.info(f"💾 Schema saved with ID: {db_schema.id}")
        
        return {
            "schema_id": db_schema.id,
            "schema": schema,
            "message": "UI schema extracted successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in UI schema extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api-schema")
async def extract_api_schema(request: APISchemaRequest, db: Session = Depends(get_db)):
    """Extract schema from API specification or sample response"""
    try:
        logger.info("🧬 Synthetic Data: Starting API schema extraction...")
        
        extractor = APISchemaExtractor()
        
        if request.openapi_spec:
            logger.info(f"📖 Extracting from OpenAPI spec for endpoint: {request.endpoint}")
            schema = extractor.extract_from_openapi(request.openapi_spec, request.endpoint)
        elif request.sample_response:
            logger.info("📑 Extracting from sample response...")
            schema = extractor.extract_from_response(request.sample_response)
        else:
            raise HTTPException(status_code=400, detail="Provide openapi_spec or sample_response")
        
        logger.info(f"✅ API schema extracted: {schema.get('total_fields', 0)} fields found")
        
        # Save to database
        db_schema = Schema(source="api", schema_json=schema)
        db.add(db_schema)
        db.commit()
        db.refresh(db_schema)
        
        logger.info(f"💾 Schema saved with ID: {db_schema.id}")
        
        return {
            "schema_id": db_schema.id,
            "schema": schema,
            "message": "API schema extracted successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in API schema extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/merge-schema")
async def merge_schemas(request: MergeSchemaRequest, db: Session = Depends(get_db)):
    """Merge UI and API schemas into unified schema"""
    try:
        merger = SchemaMerger()
        
        # Get schemas from DB or request
        if request.ui_schema_id:
            ui_schema_obj = db.query(Schema).filter(Schema.id == request.ui_schema_id).first()
            ui_schema = ui_schema_obj.schema_json if ui_schema_obj else None
        else:
            ui_schema = request.ui_schema
        
        if request.api_schema_id:
            api_schema_obj = db.query(Schema).filter(Schema.id == request.api_schema_id).first()
            api_schema = api_schema_obj.schema_json if api_schema_obj else None
        else:
            api_schema = request.api_schema
        
        # Merge schemas
        unified_schema = merger.merge(ui_schema, api_schema)
        
        # Save unified schema
        db_schema = Schema(source="unified", schema_json=unified_schema)
        db.add(db_schema)
        db.commit()
        db.refresh(db_schema)
        
        return {
            "schema_id": db_schema.id,
            "schema": unified_schema,
            "message": "Schemas merged successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_synthetic_data(request: GenerateDataRequest, db: Session = Depends(get_db)):
    """Generate synthetic data using SDV"""
    try:
        logger.info("🧬 Synthetic Data: Starting data generation...")
        
        generator = SDVGenerator()
        
        # Get schema from DB or request
        if request.schema_id:
            logger.info(f"📂 Loading schema ID: {request.schema_id}")
            schema_obj = db.query(Schema).filter(Schema.id == request.schema_id).first()
            if not schema_obj:
                raise HTTPException(status_code=404, detail="Schema not found")
            schema = schema_obj.schema_json
            schema_id = schema_obj.id
        elif request.schema:
            logger.info("📋 Using provided schema")
            schema = request.schema
            # Save schema first
            db_schema = Schema(source="direct", schema_json=schema)
            db.add(db_schema)
            db.commit()
            db.refresh(db_schema)
            schema_id = db_schema.id
        else:
            raise HTTPException(status_code=400, detail="Provide schema_id or schema")
        
        logger.info(f"🎲 Generating {request.num_rows} rows of synthetic data using {request.model_name} model...")
        
        # Generate synthetic data
        synthetic_data = generator.generate(schema, num_rows=request.num_rows, model=request.model_name)
        
        logger.info(f"✅ Successfully generated {len(synthetic_data)} rows of data")
        
        # Save run info
        run = SyntheticRun(schema_id=schema_id, rows=request.num_rows, model=request.model_name)
        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"💾 Saving data to database (Run ID: {run.id})...")
        
        # Save generated data
        for idx, row in enumerate(synthetic_data):
            data_row = SyntheticData(run_id=run.id, row_json=row)
            db.add(data_row)
        db.commit()
        
        logger.info(f"✅ Data generation complete! Run ID: {run.id}, Rows: {len(synthetic_data)}")
        
        return {
            "run_id": run.id,
            "data": synthetic_data,
            "count": len(synthetic_data),
            "message": "Synthetic data generated successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in data generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}")
async def get_synthetic_run(run_id: int, db: Session = Depends(get_db)):
    """Get synthetic data run details"""
    run = db.query(SyntheticRun).filter(SyntheticRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    data = db.query(SyntheticData).filter(SyntheticData.run_id == run_id).all()
    
    return {
        "run_id": run.id,
        "schema_id": run.schema_id,
        "rows": run.rows,
        "model": run.model,
        "created_at": run.created_at,
        "data": [d.row_json for d in data]
    }
