"""
Synthetic Data Agent Nodes
LangGraph nodes for synthetic data generation workflow
"""
import re
import json
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from agents.synthetic_data.state import SyntheticDataState
from services.synthetic.ui_schema.extractor import UISchemaExtractor
from services.synthetic.unified_schema.merger import SchemaMerger
from services.synthetic.sdv_engine.generator import SDVGenerator
from models import Schema, SyntheticRun, SyntheticData, CrawlCache
from routers.chats import append_agent_message
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _parse_json_from_llm(content: str) -> Dict[str, Any]:
    """Extract a single JSON object from LLM response (handles markdown and extra text)."""
    if not content or not content.strip():
        raise ValueError("Empty response")
    text = content.strip()
    # Remove markdown code blocks
    if "```" in text:
        for marker in ("```json", "```"):
            if marker in text:
                start = text.find(marker) + len(marker)
                end = text.find("```", start)
                if end == -1:
                    text = text[start:].strip()
                else:
                    text = text[start:end].strip()
                break
    # Find first complete JSON object
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("No complete JSON object found")


def parse_test_case_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 1: Parse test case to extract URLs and context
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 1: PARSE TEST CASE")
    logger.info("================================================================================")
    
    test_case = state['test_case']
    chat_id = state.get("chat_id")
    logger.info(f"📝 Input: {test_case[:100]}...")
    
    # Extract URLs from test case
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, test_case)
    
    if not urls:
        logger.warning("⚠️ No URLs found in test case")
        if chat_id:
            append_agent_message(db, chat_id, "Synthetic: no URLs found in test case. Stopping workflow.", None)
        return {
            **state,
            'urls': [],
            'error': "No URLs found in test case for schema extraction"
        }
    
    logger.info(f"✅ Extracted {len(urls)} URL(s): {urls}")
    if chat_id:
        append_agent_message(db, chat_id, f"Synthetic: parsed test case and found {len(urls)} URL(s) for crawling.", {"stage": "parse_test_case", "urls": urls})
    
    return {
        **state,
        'urls': urls,
        'current_step': 'crawl_pages'
    }


def crawl_pages_node(state: SyntheticDataState, db: Session) -> Dict[str, Any]:
    """
    Node 2: Crawl URLs (test-case-aware) to extract form schemas.
    Stores crawl response in temp_crawl/crawls, in DB (CrawlCache + Schema).
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 2: CRAWL PAGES (test-case-aware)")
    logger.info("================================================================================")
    
    urls = state['urls']
    test_case = state.get('test_case') or ""
    chat_id = state.get("chat_id")
    crawled_schemas = {}
    
    for url in urls:
        logger.info("🌐 Crawling: %s", url)
        if chat_id:
            append_agent_message(db, chat_id, f"Synthetic: crawling UI at {url} to infer schema…", {"stage": "crawl", "url": url})
        
        cache_entry = db.query(CrawlCache).filter(
            CrawlCache.url == url,
            CrawlCache.expires_at > datetime.utcnow()
        ).first()
        
        if cache_entry:
            logger.info("✅ Using cached schema for %s", url)
            crawled_schemas[url] = cache_entry.schema_json
            continue
        
        try:
            extractor = UISchemaExtractor()
            result = extractor.extract_from_url(url, test_case=test_case)
            schema = result.get("schema") or result
            html = result.get("html", "")
            output_dir = result.get("output_dir", "")
            
            if isinstance(schema, dict):
                num_fields = len(schema.get("fields", [])) if isinstance(schema.get("fields"), list) else len(schema.get("fields", {}))
            else:
                num_fields = 0
            logger.info("✅ Extracted schema with %s fields (saved to %s)", num_fields, output_dir or "temp_crawl")
            
            cache = CrawlCache(
                url=url,
                schema_json=schema,
                html_snapshot=html[:500000] if html else None,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.add(cache)
            db.commit()
            
            schema_row = Schema(source="ui_crawl", schema_json=schema)
            db.add(schema_row)
            db.commit()
            logger.info("💾 Crawl schema saved to DB (CrawlCache + Schema id=%s)", schema_row.id)
            
            crawled_schemas[url] = schema
            
        except Exception as e:
            logger.error("❌ Failed to crawl %s: %s", url, e)
            if chat_id:
                append_agent_message(db, chat_id, f"Synthetic: crawl failed for {url}: {e}", {"stage": "crawl_error", "url": url})
            crawled_schemas[url] = {"error": str(e)}
    
    if chat_id:
        append_agent_message(db, chat_id, "Synthetic: completed crawling for all URLs.", {"stage": "crawl_complete"})
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
    chat_id = state.get("chat_id")
    
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
        
        raw = response.choices[0].message.content or ""
        merged_schema = _parse_json_from_llm(raw)
        logger.info(f"✅ Merged schema with {len(merged_schema.get('fields', {}))} fields")
        if chat_id:
            append_agent_message(db, chat_id, f"Synthetic: merged crawled schemas into unified schema with {len(merged_schema.get('fields', {}))} fields.", {"stage": "merge_schemas"})
        
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
        if chat_id:
            append_agent_message(db, chat_id, f"Synthetic: schema merge failed: {e}", {"stage": "merge_error"})
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
    chat_id = state.get("chat_id")
    
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
        if chat_id:
            append_agent_message(db, chat_id, f"Synthetic: generated {len(synthetic_data)} rows of data (run #{run.id}).", {"stage": "generate_data", "run_id": run.id, "rows": len(synthetic_data)})
        
        return {
            **state,
            'generated_data': synthetic_data,
            'run_id': run.id,
            'current_step': 'complete'
        }
        
    except Exception as e:
        logger.error(f"❌ Data generation failed: {str(e)}")
        if chat_id:
            append_agent_message(db, chat_id, f"Synthetic: data generation failed: {e}", {"stage": "generate_error"})
        return {
            **state,
            'error': f"Data generation failed: {str(e)}"
        }
