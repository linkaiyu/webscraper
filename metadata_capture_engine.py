import hashlib
import json
from playwright.async_api import Page, ElementHandle
from typing import Dict, Any, List, Optional
import asyncio

class MetadataCaptureEngine:
    """
    Captures all metadata needed to generate a scraper.
    Acts as an authoring tool for Copilot.
    """
    
    def __init__(self):
        self.workflow = None
        self.current_step = 0
        self.observed_selectors = {}  # Track which selectors work
        self.selector_failures = {}  # Track failed selectors
        self.page_history = []  # Track navigation history
        self.interaction_context = {}  # Track state
    
    async def record_session(self, page: Page, user_instruction: str) -> ScraperWorkflow:
        """Start recording a user session for automation authoring"""
        
        # Initialize workflow
        self.workflow = ScraperWorkflow(
            id=f"workflow_{datetime.now().timestamp()}",
            name=f"Scraper for {await page.title()}",
            description=user_instruction,
            entry_url=page.url,
            steps=[],
            pagination=PaginationPattern(type="unknown"),
            extraction=ExtractionSchema(fields={})
        )
        
        # Start observing
        await self._observe_page(page, "initial")
        
        return self.workflow
    
    async def record_action(self, page: Page, action_type: ActionType, 
                           description: str, **kwargs) -> NavigationAction:
        """Record a user action for playback"""
        
        # Identify the best selector for this action
        selector = await self._identify_selector(page, action_type, kwargs)
        
        # Capture page state before action
        structure_before = await self._capture_page_structure(page)
        
        # Record the action
        action = NavigationAction(
            id=f"step_{self.current_step}",
            type=action_type,
            description=description,
            selector=selector,
            selector_strategies=await self._generate_selector_strategies(page, kwargs),
            value=kwargs.get('value'),
            wait_for=kwargs.get('wait_for'),
            metadata=kwargs
        )
        
        # Add to workflow
        step = WorkflowStep(
            id=f"step_{self.current_step}",
            order=self.current_step,
            action=action,
            page_structure=structure_before
        )
        
        self.workflow.steps.append(step)
        self.current_step += 1
        
        # Observe after action
        await self._observe_page(page, f"after_action_{action.id}")
        
        return action
    
    async def detect_pagination(self, page: Page) -> PaginationPattern:
        """Automatically detect pagination patterns"""
        
        pattern = PaginationPattern(type="unknown")
        
        # 1. Check for next/prev buttons
        next_prev = await page.evaluate("""
            () => {
                const patterns = {
                    next: ['.next', '.next-page', '[rel="next"]', 
                           '.pagination .next', '.pager .next'],
                    prev: ['.prev', '.prev-page', '[rel="prev"]',
                           '.pagination .prev', '.pager .prev']
                };
                
                const findSelector = (patterns) => {
                    for (const selector of patterns) {
                        if (document.querySelector(selector)) return selector;
                    }
                    return null;
                };
                
                return {
                    next: findSelector(patterns.next),
                    prev: findSelector(patterns.prev)
                };
            }
        """)
        
        if next_prev['next']:
            pattern.type = "next_prev"
            pattern.next_button_selector = next_prev['next']
            pattern.prev_button_selector = next_prev['prev']
        
        # 2. Check for numbered pagination
        numbered = await page.evaluate("""
            () => {
                const selectors = ['.pagination a', '.page-numbers', '.pages a'];
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 2) {
                        const numbers = Array.from(elements)
                            .map(el => el.textContent.trim())
                            .filter(t => !isNaN(t));
                        if (numbers.length > 1) {
                            return {
                                selector: selector,
                                numbers: numbers,
                                current: document.querySelector('.active, .current')?.textContent
                            };
                        }
                    }
                }
                return null;
            }
        """)
        
        if numbered and len(numbered['numbers']) > 1:
            pattern.type = "numbered"
            pattern.page_number_selector = numbered['selector']
            pattern.current_page_selector = '.active, .current'
            pattern.max_pages = len(numbered['numbers'])
        
        # 3. Check for infinite scroll / load more
        load_more = await page.evaluate("""
            () => {
                const selectors = [
                    '.load-more', '.show-more', '.view-more',
                    '[data-load-more]', '.infinite-scroll-trigger',
                    'button:contains("Load More")', 'a:contains("Show More")'
                ];
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el) {
                        return {
                            selector: selector,
                            text: el.textContent.trim(),
                            is_button: el.tagName === 'BUTTON'
                        };
                    }
                }
                return null;
            }
        """)
        
        if load_more:
            pattern.type = "load_more"
            pattern.load_more_selector = load_more['selector']
        
        # 4. Detect scroll-based loading
        scroll_based = await page.evaluate("""
            () => {
                // Check if content loads on scroll
                const hasLazyImages = document.querySelector('img[data-src]') !== null;
                const infiniteScroll = document.querySelector('[data-infinite-scroll]') !== null;
                const hasIntersectionObserver = !!window.IntersectionObserver;
                
                return {
                    has_lazy_images: hasLazyImages,
                    has_infinite_scroll: infiniteScroll,
                    uses_intersection_observer: hasIntersectionObserver
                };
            }
        """)
        
        if scroll_based['has_lazy_images'] or scroll_based['has_infinite_scroll']:
            pattern.type = "infinite_scroll"
            pattern.scroll_trigger = "bottom"
            pattern.stop_condition = "no_more_content"
        
        # Store observed patterns
        pattern.observed_patterns.append({
            'url': page.url,
            'detected': datetime.now().isoformat(),
            'page_height': await page.evaluate("document.body.scrollHeight")
        })
        
        self.workflow.pagination = pattern
        return pattern
    
    async def capture_extraction_schema(self, page: Page, sample_count: int = 3) -> ExtractionSchema:
        """Capture schema from sample detail pages"""
        
        schema = ExtractionSchema(fields={})
        
        # Get sample of products/listings
        products = await page.evaluate("""
            (count) => {
                const selectors = [
                    '.product', '.product-item', '.product-card', 
                    '.listing-item', '.item', '.result',
                    '[data-product-id]', '[data-item-id]'
                ];
                
                let items = [];
                for (const sel of selectors) {
                    const found = document.querySelectorAll(sel);
                    if (found.length >= count) {
                        items = Array.from(found).slice(0, count);
                        break;
                    }
                }
                
                return items.map(el => ({
                    html: el.outerHTML,
                    tagName: el.tagName,
                    className: el.className,
                    id: el.id,
                    text: el.textContent.trim().slice(0, 500)
                }));
            }
        """, sample_count)
        
        # Analyze each sample to find common patterns
        for i, product_data in enumerate(products):
            # Extract possible fields
            fields = await self._analyze_sample_fields(page, product_data)
            for field_name, field_info in fields.items():
                if field_name not in schema.fields:
                    schema.fields[field_name] = field_info
                else:
                    # Merge and strengthen confidence
                    self._merge_field_info(schema.fields[field_name], field_info)
        
        self.workflow.extraction = schema
        return schema
    
    async def _analyze_sample_fields(self, page: Page, sample: Dict) -> Dict[str, Any]:
        """Analyze a sample element to find extractable fields"""
        
        fields = {}
        
        # Common field patterns
        patterns = {
            'name': ['h1', 'h2', 'h3', '.name', '.title', '.product-name', '.item-name'],
            'price': ['.price', '.product-price', '.price-tag', '[data-price]', '.cost'],
            'description': ['.description', '.desc', '.product-description', '.details'],
            'sku': ['.sku', '.product-sku', '[data-sku]', '.item-number'],
            'brand': ['.brand', '.manufacturer', '.byline', '.vendor'],
            'rating': ['.rating', '.stars', '.review-stars', '.product-rating'],
            'image': ['img', '.product-image', '.item-image', '[data-image]']
        }
        
        # Try each field pattern
        for field_name, selectors in patterns.items():
            for selector in selectors:
                # Check if selector exists in sample
                if selector.startswith('.'):
                    # CSS class check
                    if selector[1:] in sample['className']:
                        fields[field_name] = {
                            'selector': selector,
                            'type': 'text',
                            'confidence': 0.8,
                            'sample_value': await self._extract_value(page, selector, sample)
                        }
                        break
                elif selector.startswith('['):
                    # Data attribute check
                    attr_name = selector[1:-1]
                    if attr_name in sample['html']:
                        fields[field_name] = {
                            'selector': selector,
                            'type': 'attribute',
                            'confidence': 0.7,
                            'sample_value': await self._extract_value(page, selector, sample)
                        }
                        break
        
        return fields
    
    async def generate_workflow(self, page: Page, user_intent: str) -> ScraperWorkflow:
        """
        Generate complete workflow from recorded session
        """
        
        # 1. Detect pagination
        pagination = await self.detect_pagination(page)
        
        # 2. Capture extraction schema from sample
        schema = await self.capture_extraction_schema(page)
        
        # 3. Analyze navigation patterns
        nav_patterns = await self._analyze_navigation_patterns(page)
        
        # 4. Generate site fingerprint
        fingerprint = await self._generate_site_fingerprint(page)
        
        # 5. Build complete workflow
        workflow = ScraperWorkflow(
            id=f"workflow_{datetime.now().timestamp()}",
            name=f"Scraper for {await page.title()}",
            description=user_intent,
            entry_url=page.url,
            steps=self.workflow.steps if self.workflow else [],
            pagination=pagination,
            extraction=schema,
            site_fingerprint=fingerprint,
            generated_at=datetime.now(),
            version=1
        )
        
        return workflow
    
    async def _generate_site_fingerprint(self, page: Page) -> str:
        """Generate a unique fingerprint for the site"""
        
        fingerprint_data = await page.evaluate("""
            () => {
                return {
                    domain: window.location.hostname,
                    doctype: document.doctype?.name,
                    html_classes: document.documentElement.className,
                    body_classes: document.body.className,
                    meta: Array.from(document.querySelectorAll('meta')).map(m => ({
                        name: m.name,
                        property: m.property,
                        content: m.content
                    })),
                    scripts: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
                    css: Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href)
                };
            }
        """)
        
        # Create hash
        json_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()[:16]
    
    async def _analyze_navigation_patterns(self, page: Page) -> Dict[str, Any]:
        """Analyze how navigation works on the site"""
        
        patterns = await page.evaluate("""
            () => {
                const patterns = {
                    breadcrumbs: [],
                    categories: [],
                    filters: [],
                    sort_options: []
                };
                
                // Detect breadcrumbs
                const breadcrumbSelectors = [
                    '.breadcrumb', '.breadcrumbs', '.nav-breadcrumbs',
                    '[aria-label="breadcrumb"]'
                ];
                for (const sel of breadcrumbSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        patterns.breadcrumbs = Array.from(el.querySelectorAll('a'))
                            .map(a => a.textContent.trim());
                        break;
                    }
                }
                
                // Detect category navigation
                const categorySelectors = [
                    '.category', '.categories', '.nav-category',
                    '.product-category', '.department'
                ];
                for (const sel of categorySelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        patterns.categories = Array.from(el.querySelectorAll('a'))
                            .map(a => ({
                                text: a.textContent.trim(),
                                href: a.href
                            }));
                        break;
                    }
                }
                
                // Detect filters
                const filterSelectors = [
                    '.filter', '.filters', '.sidebar-filter',
                    '.filter-options', '.refinement'
                ];
                for (const sel of filterSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        patterns.filters = Array.from(el.querySelectorAll('input, select'))
                            .map(input => ({
                                type: input.type,
                                name: input.name,
                                options: Array.from(input.options || []).map(o => o.text)
                            }));
                        break;
                    }
                }
                
                return patterns;
            }
        """)
        
        return patterns
    
    async def _identify_selector(self, page: Page, action_type: ActionType, 
                                kwargs: Dict) -> str:
        """Intelligently identify the best selector for an action"""
        
        if 'selector' in kwargs:
            # User provided selector
            return kwargs['selector']
        
        if 'text' in kwargs:
            # Find element by text
            text = kwargs['text']
            selector = f"text='{text}'"
            try:
                await page.locator(selector).first.wait_for(timeout=1000)
                return selector
            except:
                pass
        
        # Try to infer from action type
        if action_type == ActionType.CLICK:
            # Look for buttons/links with matching description
            desc = kwargs.get('description', '')
            results = await page.evaluate(f"""
                () => {{
                    const items = [];
                    const buttons = document.querySelectorAll('button, a, [role="button"]');
                    for (const el of buttons) {{
                        const text = el.textContent.trim().toLowerCase();
                        if (text.includes('{desc.lower()}')) {{
                            items.push({{
                                selector: el.id ? `#${{el.id}}` : null,
                                text: text
                            }});
                        }}
                    }}
                    return items.length > 0 ? items[0] : null;
                }}
            """)
            
            if results and results['selector']:
                return results['selector']
        
        # Default fallback
        return kwargs.get('default_selector', 'body')
    
    async def _generate_selector_strategies(self, page: Page, 
                                          kwargs: Dict) -> List[SelectorStrategy]:
        """Generate multiple selector strategies for robustness"""
        
        strategies = []
        
        # CSS selector (if provided)
        if 'selector' in kwargs:
            strategies.append(SelectorStrategy.CSS)
        
        # Text-based (if applicable)
        if 'text' in kwargs or 'description' in kwargs:
            strategies.append(SelectorStrategy.TEXT)
        
        # Data attribute (common in modern web)
        strategies.append(SelectorStrategy.DATA_ATTR)
        
        # Role (ARIA)
        strategies.append(SelectorStrategy.ROLE)
        
        return strategies
    
    async def _capture_page_structure(self, page: Page) -> PageStructure:
        """Capture the current page structure"""
        
        structure_data = await page.evaluate("""
            () => ({
                url: window.location.href,
                title: document.title,
                interactive: Array.from(document.querySelectorAll(
                    'button, a, input, select, textarea, [role="button"]'
                )).map(el => ({
                    tag: el.tagName,
                    text: el.textContent.trim().slice(0, 50),
                    selector: el.id ? `#${el.id}` : null,
                    classes: el.className
                })).slice(0, 20),
                forms: Array.from(document.forms).map(form => ({
                    action: form.action,
                    method: form.method,
                    fields: Array.from(form.elements).map(el => ({
                        name: el.name,
                        type: el.type,
                        value: el.value
                    }))
                })),
                dynamic: Array.from(document.querySelectorAll(
                    '[data-*], [class*="js-"], [ng-*], [v-*]'
                )).map(el => el.tagName).slice(0, 10)
            })
        """)
        
        return PageStructure(
            url=structure_data['url'],
            title=structure_data['title'],
            detected_patterns={},
            interactive_elements=structure_data['interactive'],
            forms=structure_data['forms'],
            dynamic_elements=structure_data['dynamic'],
            load_triggers=[],
            timestamp=datetime.now()
        )
    
    async def _observe_page(self, page: Page, context: str):
        """Observe and learn from page behavior"""
        
        observation = await page.evaluate("""
            () => {
                return {
                    url: window.location.href,
                    title: document.title,
                    has_products: document.querySelector('.product, .product-item, .listing-item') !== null,
                    has_pagination: document.querySelector('.pagination, .pages, .load-more') !== null,
                    content_count: document.querySelectorAll('.product, .item, .result').length,
                    load_triggers: Array.from(document.querySelectorAll(
                        '.load-more, .show-more, [data-infinite-scroll]'
                    )).map(el => ({
                        selector: el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`,
                        text: el.textContent.trim()
                    }))
                };
            }
        """)
        
        # Store observation for learning
        self.observed_selectors[context] = observation