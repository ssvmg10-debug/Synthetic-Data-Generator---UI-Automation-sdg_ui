"""
Synthetic Data Agent Nodes
LangGraph nodes for synthetic data generation workflow
"""
import re
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from agents.synthetic_data.state import SyntheticDataState
from services.synthetic.ui_schema.extractor import UISchemaExtractor
from services.synthetic.unified_schema.merger import SchemaMerger
from services.synthetic.sdv_engine.generator import SDVGenerator
from models import Schema, SyntheticRun, SyntheticData, CrawlCache
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def parse_test_case_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 1: Parse test case to extract URLs and context
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 1: PARSE TEST CASE")
    logger.info("================================================================================")
    
    test_case = state['test_case']
    logger.info(f"📝 Input: {test_case[:100]}...")
    
    # Extract URLs from test case
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, test_case)
    
    if not urls:
        logger.warning("⚠️ No URLs found in test case")
        return {
            **state,
            'urls': [],
            'error': "No URLs found in test case for schema extraction"
        }
    
    logger.info(f"✅ Extracted {len(urls)} URL(s): {urls}")
    
    return {
        **state,
        'urls': urls,
        'current_step': 'crawl_pages'
    }


def crawl_pages_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 2: Crawl URLs to extract form schemas
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 2: CRAWL PAGES")
    logger.info("================================================================================")
    
    urls = state['urls']
    crawled_schemas = {}
    
    for url in urls:
        logger.info(f"🌐 Crawling: {url}")
        
        # Check cache first
        cache_entry = db.query(CrawlCache).filter(
            CrawlCache.url == url,
            CrawlCache.expires_at > datetime.utcnow()
        ).first()
        
        if cache_entry:
            logger.info(f"✅ Using cached schema for {url}")
            crawled_schemas[url] = cache_entry.schema_json
            continue
        
        # Crawl the page
        try:
            extractor = UISchemaExtractor()
            schema = extractor.extract_from_url(url)
            
            # Cache the result
            cache = CrawlCache(
                url=url,
                schema_json=schema,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.add(cache)
            db.commit()
            
            crawled_schemas[url] = schema
            logger.info(f"✅ Extracted schema with {len(schema.get('fields', {}))} fields")
            
        except Exception as e:
            logger.error(f"❌ Failed to crawl {url}: {str(e)}")
            crawled_schemas[url] = {"error": str(e)}
    
    return {
        **state,
        'crawled_schemas': crawled_schemas,
        'current_step': 'merge_schemas'
    }


def merge_schemas_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 3: Merge test case context + crawler schemas
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 3: MERGE SCHEMAS")
    logger.info("================================================================================")
    
    test_case = state['test_case']
    crawled_schemas = state['crawled_schemas']
    
    # Use Azure OpenAI to intelligently merge schemas
    from utils.azure_openai import get_openai_client
    import os
    import json
    
    client = get_openai_client()
    
    system_prompt = """You are a data schema expert. Analyze the test case and crawled schemas to create a unified schema.

Extract:
1. Field names mentioned in test case or found in forms
2. Field types (string, integer, float, email, phone, address, name, datetime)
3. Required fields

Return JSON:
{
    "fields": {
        "field_name": {"type": "string", "required": true}
    }
}
"""
    
    user_prompt = f"""Test Case:\n{test_case}\n\nCrawled Schemas:\n{json.dumps(crawled_schemas, indent=2)}"""
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        
        merged_schema = json.loads(response.choices[0].message.content)
        logger.info(f"✅ Merged schema with {len(merged_schema.get('fields', {}))} fields")
        
        # Save schema to database
        db_schema = Schema(source="test_case_crawl", schema_json=merged_schema)
        db.add(db_schema)
        db.commit()
        db.refresh(db_schema)
        
        logger.info(f"💾 Schema saved with ID: {db_schema.id}")
        
        return {
            **state,
            'merged_schema': merged_schema,
            'schema_id': db_schema.id,
            'current_step': 'generate_data'
        }
        
    except Exception as e:
        logger.error(f"❌ Schema merge failed: {str(e)}")
        return {
            **state,
            'error': f"Schema merge failed: {str(e)}"
        }


def generate_data_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 4: Generate synthetic data
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 4: GENERATE SYNTHETIC DATA")
    logger.info("================================================================================")
    
    merged_schema = state['merged_schema']
    num_rows = state.get('num_rows', 10)
    schema_id = state['schema_id']
    
    logger.info(f"🎲 Generating {num_rows} rows...")
    
    try:
        # Normalize schema format for SDVGenerator.
        # LLM merge may return:
        #   { "fields": { "email": {"type":"string", ...}, "age": {"type":"integer"} } }
        # while SDVGenerator expects:
        #   { "fields": [ {"name":"email","type":"string",...}, {"name":"age","type":"integer"} ] }
        if isinstance(merged_schema, dict):
            fields = merged_schema.get("fields")
            if isinstance(fields, dict):
                normalized = []
                for name, spec in fields.items():
                    if isinstance(spec, dict):
                        item = {"name": str(name), **spec}
                    else:
                        item = {"name": str(name), "type": "string"}
                    normalized.append(item)
                merged_schema = {**merged_schema, "fields": normalized, "total_fields": len(normalized)}
            elif isinstance(fields, list):
                normalized = []
                for f in fields:
                    if isinstance(f, dict) and f.get("name"):
                        normalized.append(f)
                    elif isinstance(f, str):
                        normalized.append({"name": f, "type": "string"})
                merged_schema = {**merged_schema, "fields": normalized, "total_fields": len(normalized)}

        generator = SDVGenerator()
        synthetic_data = generator.generate(merged_schema, num_rows=num_rows, model="GaussianCopula")
        
        logger.info(f"✅ Generated {len(synthetic_data)} rows")
        
        # Save run
        run = SyntheticRun(schema_id=schema_id, rows=num_rows, model="GaussianCopula")
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Save data
        for row in synthetic_data:
            data_row = SyntheticData(run_id=run.id, row_json=row)
            db.add(data_row)
        db.commit()
        
        logger.info(f"💾 Saved run with ID: {run.id}")
        logger.info("================================================================================")
        logger.info("🎉 WORKFLOW COMPLETE")
        logger.info("================================================================================")
        
        return {
            **state,
            'generated_data': synthetic_data,
            'run_id': run.id,
            'current_step': 'complete'
        }
        
    except Exception as e:
        logger.error(f"❌ Data generation failed: {str(e)}")
        return {
            **state,
            'error': f"Data generation failed: {str(e)}"
        }
