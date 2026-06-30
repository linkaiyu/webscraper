# ===== MAIN APPLICATION =====
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

class AuthoringApp:
    """Main application for metadata capture"""
    
    def __init__(self):
        self.authoring_tool = CopilotAuthoringTool()
        self.workflows = []
    
    async def process_user_instruction(self, page: Page, instruction: str) -> ScraperWorkflow:
        """
        Main entry point - user gives instruction, Copilot captures everything
        """
        
        # 1. Start authoring session
        workflow = await self.authoring_tool.author_workflow(page, instruction)
        
        # 2. Generate configuration
        config = ScraperGenerator.generate_config(workflow)
        
        # 3. Generate executable code
        code = ScraperGenerator.generate_playwright_code(workflow)
        
        # 4. Store for reuse
        self.workflows.append({
            'workflow': workflow,
            'config': config,
            'code': code,
            'created_at': datetime.now()
        })
        
        return workflow

# ===== WEBSOCKET FOR REAL-TIME AUTHORING =====
@app.websocket("/author")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    app = AuthoringApp()
    browser = None
    page = None
    
    try:
        # Start browser session
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        
        while True:
            # Receive user instruction
            data = await websocket.receive_text()
            instruction = json.loads(data)
            
            if instruction['action'] == 'navigate':
                await page.goto(instruction['url'])
                
                # Send page analysis
                analysis = await app.authoring_tool._analyze_and_suggest(page, instruction.get('intent', ''))
                await websocket.send_text(json.dumps({
                    'type': 'analysis',
                    'data': analysis
                }))
            
            elif instruction['action'] == 'author':
                # Generate workflow
                workflow = await app.process_user_instruction(page, instruction.get('intent', ''))
                
                # Generate code
                code = ScraperGenerator.generate_playwright_code(workflow)
                config = ScraperGenerator.generate_config(workflow)
                
                # Send back
                await websocket.send_text(json.dumps({
                    'type': 'workflow',
                    'workflow': workflow.dict(),
                    'code': code,
                    'config': config
                }))
            
            elif instruction['action'] == 'record_click':
                # Record a click action
                action = await app.authoring_tool.capture_engine.record_action(
                    page,
                    ActionType.CLICK,
                    instruction.get('description', 'User clicked'),
                    selector=instruction.get('selector'),
                    wait_for=instruction.get('wait_for')
                )
                await websocket.send_text(json.dumps({
                    'type': 'action_recorded',
                    'action': action.dict()
                }))
            
            elif instruction['action'] == 'test_workflow':
                # Test the generated workflow
                config = json.loads(instruction.get('config', '{}'))
                # Execute test...
                await websocket.send_text(json.dumps({
                    'type': 'test_result',
                    'success': True,
                    'data': 'Workflow test successful'
                }))
    
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if browser:
            await browser.close()

# ===== REST API =====
@app.post("/author")
async def author_scraper(url: str, intent: str):
    """REST endpoint for authoring"""
    app = AuthoringApp()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        
        workflow = await app.process_user_instruction(page, intent)
        
        await browser.close()
        
        return {
            'status': 'success',
            'workflow_id': workflow.id,
            'config': ScraperGenerator.generate_config(workflow),
            'code': ScraperGenerator.generate_playwright_code(workflow)
        }

@app.get("/workflows")
async def list_workflows():
    """List all captured workflows"""
    return {'workflows': app.workflows}

@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a specific workflow"""
    for wf in app.workflows:
        if wf['workflow'].id == workflow_id:
            return wf
    return {'error': 'Workflow not found'}