class CopilotAuthoringTool:
    """
    Copilot acts as an intelligent authoring assistant.
    It captures user interactions and generates reusable workflows.
    """
    
    def __init__(self):
        self.capture_engine = MetadataCaptureEngine()
        self.workflow_history = []
        self.selector_confidence = {}  # Track successful selectors
        self.common_patterns = self._load_common_patterns()
    
    async def author_workflow(self, page: Page, user_instruction: str) -> ScraperWorkflow:
        """
        Main authoring flow - Copilot guides user through capturing
        """
        
        # 1. Start recording session
        await self.capture_engine.record_session(page, user_instruction)
        
        # 2. Analyze page and provide suggestions
        suggestions = await self._analyze_and_suggest(page, user_instruction)
        
        # 3. Let user/copilot interact and capture steps
        steps = await self._capture_user_journey(page, suggestions)
        
        # 4. Generate workflow
        workflow = await self.capture_engine.generate_workflow(page, user_instruction)
        
        # 5. Store in history
        self.workflow_history.append(workflow)
        
        return workflow
    
    async def _analyze_and_suggest(self, page: Page, intent: str) -> Dict[str, Any]:
        """Analyze page and suggest next actions"""
        
        analysis = await page.evaluate("""
            () => {
                const suggestions = {
                    actions: [],
                    detected_patterns: []
                };
                
                // Detect product lists
                const productSelectors = [
                    '.product', '.product-item', '.product-card', 
                    '.listing-item', '.item', '.result'
                ];
                for (const sel of productSelectors) {
                    const count = document.querySelectorAll(sel).length;
                    if (count > 0) {
                        suggestions.detected_patterns.push({
                            type: 'product_list',
                            selector: sel,
                            count: count
                        });
                        suggestions.actions.push(
                            `Click on a ${sel} to capture detail page pattern`
                        );
                        break;
                    }
                }
                
                // Detect pagination
                const paginationSelectors = [
                    '.pagination', '.pages', '.next', '.load-more'
                ];
                for (const sel of paginationSelectors) {
                    if (document.querySelector(sel)) {
                        suggestions.detected_patterns.push({
                            type: 'pagination',
                            selector: sel
                        });
                        suggestions.actions.push(
                            `Navigate to next page to capture pagination pattern`
                        );
                        break;
                    }
                }
                
                // Detect categories/menu
                const navSelectors = [
                    '.nav', '.menu', '.categories', '.category-list'
                ];
                for (const sel of navSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.querySelectorAll('a').length > 0) {
                        suggestions.detected_patterns.push({
                            type: 'navigation',
                            selector: sel
                        });
                        suggestions.actions.push(
                            'Navigate through categories to map site structure'
                        );
                        break;
                    }
                }
                
                return suggestions;
            }
        """)
        
        return analysis
    
    async def _capture_user_journey(self, page: Page, suggestions: Dict) -> List[WorkflowStep]:
        """Capture the user's navigation journey"""
        
        steps = []
        
        # 1. Capture navigation to product list
        nav_step = await self.capture_engine.record_action(
            page,
            ActionType.NAVIGATE,
            "Navigate to product list",
            url=page.url
        )
        steps.append(nav_step)
        
        # 2. If there are categories, capture selection
        if suggestions.get('detected_patterns'):
            for pattern in suggestions['detected_patterns']:
                if pattern['type'] == 'navigation':
                    # Record category selection
                    category_step = await self.capture_engine.record_action(
                        page,
                        ActionType.CLICK,
                        f"Select category from {pattern['selector']}",
                        selector=pattern['selector'],
                        wait_for='.product, .product-item'
                    )
                    steps.append(category_step)
        
        # 3. Detect and capture pagination
        pagination = await self.capture_engine.detect_pagination(page)
        
        if pagination.type == 'next_prev':
            pagination_step = await self.capture_engine.record_action(
                page,
                ActionType.PAGINATE,
                "Navigate through all pages",
                next_selector=pagination.next_button_selector,
                max_pages=pagination.max_pages or 5
            )
            steps.append(pagination_step)
        
        # 4. Capture product detail pattern
        product_sample = await self._capture_product_detail_pattern(page)
        if product_sample:
            detail_step = await self.capture_engine.record_action(
                page,
                ActionType.EXTRACT,
                "Extract product details from detail page",
                extraction_schema=product_sample
            )
            steps.append(detail_step)
        
        return steps
    
    async def _capture_product_detail_pattern(self, page: Page) -> Dict[str, Any]:
        """Capture the pattern of product detail pages"""
        
        # Find a product to click
        product_link = await page.evaluate("""
            () => {
                const selectors = [
                    '.product a', '.product-item a', '.product-card a',
                    '.listing-item a', '.item a', 'a[href*="/product/"]'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.href) {
                        return {
                            selector: sel,
                            href: el.href,
                            text: el.textContent.trim()
                        };
                    }
                }
                return null;
            }
        """)
        
        if not product_link:
            return None
        
        # Navigate to detail page
        await page.goto(product_link['href'], wait_until='networkidle')
        
        # Capture detail page structure
        detail_structure = await page.evaluate("""
            () => {
                const extract = {
                    name: document.querySelector('h1, .product-name, .title')?.textContent?.trim(),
                    price: document.querySelector('.price, .product-price, .price-tag')?.textContent?.trim(),
                    description: document.querySelector('.description, .product-description, .desc')?.textContent?.trim(),
                    sku: document.querySelector('.sku, .product-sku')?.textContent?.trim(),
                    brand: document.querySelector('.brand, .manufacturer')?.textContent?.trim(),
                    images: Array.from(document.querySelectorAll('.product-image img, .gallery img'))
                        .map(img => img.src),
                    attributes: {}
                };
                
                // Capture any attribute tables
                const attrRows = document.querySelectorAll('.attributes tr, .specifications tr');
                attrRows.forEach(row => {
                    const key = row.querySelector('th, .label')?.textContent?.trim();
                    const value = row.querySelector('td, .value')?.textContent?.trim();
                    if (key && value) {
                        extract.attributes[key] = value;
                    }
                });
                
                return extract;
            }
        """)
        
        return detail_structure