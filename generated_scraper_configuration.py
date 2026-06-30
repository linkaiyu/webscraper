class ScraperGenerator:
    """
    Generates a reusable scraper from captured metadata
    """
    
    @staticmethod
    def generate_config(workflow: ScraperWorkflow) -> Dict[str, Any]:
        """Generate a reusable configuration from captured workflow"""
        
        config = {
            "workflow_id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "entry_url": workflow.entry_url,
            "site_fingerprint": workflow.site_fingerprint,
            "generated_at": workflow.generated_at.isoformat(),
            
            "navigation": {
                "steps": []
            },
            
            "pagination": {
                "type": workflow.pagination.type,
                "config": {
                    "next_selector": workflow.pagination.next_button_selector,
                    "load_more_selector": workflow.pagination.load_more_selector,
                    "max_pages": workflow.pagination.max_pages,
                    "stop_condition": workflow.pagination.stop_condition
                }
            },
            
            "extraction": {
                "fields": workflow.extraction.fields,
                "schema_version": "1.0"
            },
            
            "selectors": {
                "dynamic": [],  # Will be filled during execution
                "fallbacks": {}  # Alternative selectors
            }
        }
        
        # Convert steps to config
        for step in workflow.steps:
            step_config = {
                "id": step.id,
                "type": step.action.type,
                "description": step.action.description,
                "selector": step.action.selector,
                "wait_for": step.action.wait_for,
                "timeout": step.timeout,
                "retry_count": step.retry_count
            }
            
            if step.action.type == ActionType.PAGINATE:
                step_config["pagination"] = {
                    "next_selector": workflow.pagination.next_button_selector,
                    "max_pages": workflow.pagination.max_pages
                }
            
            if step.action.type == ActionType.EXTRACT:
                step_config["extraction"] = workflow.extraction.fields
            
            config["navigation"]["steps"].append(step_config)
        
        return config
    
    @staticmethod
    def generate_playwright_code(workflow: ScraperWorkflow) -> str:
        """Generate executable Playwright code from workflow"""
        
        code = f'''
import asyncio
from playwright.async_api import async_playwright

async def scrape_workflow():
    """Generated scraper for {workflow.name}"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to entry URL
        await page.goto("{workflow.entry_url}", wait_until="networkidle")
        
        # Execute steps
        {ScraperGenerator._generate_step_code(workflow)}
        
        # Pagination
        {ScraperGenerator._generate_pagination_code(workflow)}
        
        # Extract data
        {ScraperGenerator._generate_extraction_code(workflow)}
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_workflow())
'''
        return code
    
    @staticmethod
    def _generate_step_code(workflow: ScraperWorkflow) -> str:
        """Generate code for each workflow step"""
        
        code_lines = []
        for step in workflow.steps:
            if step.action.type == ActionType.CLICK:
                code_lines.append(f'''
        # Step: {step.action.description}
        await page.click("{step.action.selector}")
        await page.wait_for_selector("{step.action.wait_for}", timeout={step.timeout})
''')
            elif step.action.type == ActionType.NAVIGATE:
                code_lines.append(f'''
        # Step: {step.action.description}
        await page.goto("{step.action.value}", wait_until="networkidle")
''')
            elif step.action.type == ActionType.WAIT:
                code_lines.append(f'''
        # Step: {step.action.description}
        await page.wait_for_timeout({step.action.timeout})
''')
        
        return '\n'.join(code_lines)
    
    @staticmethod
    def _generate_pagination_code(workflow: ScraperWorkflow) -> str:
        """Generate pagination handling code"""
        
        if workflow.pagination.type == "next_prev":
            return f'''
        # Pagination: Next/Prev buttons
        all_data = []
        page_num = 1
        while True:
            # Extract data from current page
            data = await extract_current_page(page)
            all_data.extend(data)
            
            # Check for next button
            next_button = await page.query_selector("{workflow.pagination.next_button_selector}")
            if not next_button or {workflow.pagination.max_pages and f"page_num >= {workflow.pagination.max_pages}"}:
                break
                
            await next_button.click()
            await page.wait_for_load_state("networkidle")
            page_num += 1
'''
        
        elif workflow.pagination.type == "load_more":
            return f'''
        # Pagination: Load More button
        all_data = []
        while True:
            # Extract current data
            data = await extract_current_page(page)
            all_data.extend(data)
            
            # Check for load more
            load_more = await page.query_selector("{workflow.pagination.load_more_selector}")
            if not load_more or await load_more.is_disabled():
                break
                
            await load_more.click()
            await page.wait_for_timeout(1000)  # Wait for content to load
'''
        
        elif workflow.pagination.type == "infinite_scroll":
            return f'''
        # Pagination: Infinite Scroll
        all_data = []
        last_height = 0
        scroll_attempts = 0
        
        while scroll_attempts < 10:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            
            # Check if new content loaded
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_height = new_height
            
            # Extract current data
            data = await extract_current_page(page)
            all_data.extend(data)
        
        # Remove duplicates
        all_data = list({{d['id']: d for d in all_data}}.values())
'''
        
        return ""
    
    @staticmethod
    def _generate_extraction_code(workflow: ScraperWorkflow) -> str:
        """Generate extraction code"""
        
        extraction_code = '''
    async def extract_current_page(page):
        """Extract data from current page"""
        data = []
        
        # Find product containers
        containers = await page.query_selector_all('.product, .product-item, .product-card')
        
        for container in containers:
            item = {}
'''
        
        for field_name, field_info in workflow.extraction.fields.items():
            selector = field_info.get('selector', '')
            extraction_code += f'''
            # Extract {field_name}
            el = await container.query_selector('{selector}')
            if el:
                item['{field_name}'] = await el.text_content()
'''
        
        extraction_code += '''
            if item:
                data.append(item)
        
        return data
'''
        
        return extraction_code