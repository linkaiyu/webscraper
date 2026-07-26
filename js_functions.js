// from DeepSeek, support get_nearby_text('marker', 'after/..' | 'before/..')
// 'contains' | 'startswith' | 'endswith'
/*
PRICE = get_nearby_text('CONTEXT', 'before/..') -> 'PRICE\n\n$5/M tokens'
CONTEXT = get_nearby_text('PRICE', 'after/..')  -> 'CONTEXT\n\n4K'

Released = get_nearby_text('RELEASED', 'after') ->'Jul 23, 2026'

Providers = get_nearby_text('Uptime', 'after/..') ->'Azure\n\t$5.00\t$8.00\t$108.00\t0.01s\t37 tps\t\n100.00%'
Weighted_Avg_Input_Price = get_nearby_text('Weighted Avg Input Price', 'after') ->'$6.74'
Weighted_Avg_Output_Price = get_nearby_text('Weighted Avg Output Price', 'after') ->'$108.00'
*/


function get_nearby_text(marker, position = 'after', matchMode = 'exact') {
    if (typeof marker !== 'string' || marker === '') return '';
    
    matchMode = String(matchMode || 'exact').toLowerCase();
    
    const body = document.body;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_ELEMENT);
    let node;
    
    function isMatch(text) {
        if (!text) return false;
        const normalizedText = text.toLowerCase().trim();
        const normalizedMarker = marker.toLowerCase().trim();
        
        switch(matchMode) {
            case 'exact': return normalizedText === normalizedMarker;
            case 'contains': return normalizedText.includes(normalizedMarker);
            case 'startswith': return normalizedText.startsWith(normalizedMarker);
            case 'endswith': return normalizedText.endsWith(normalizedMarker);
            case 'regex':
                try { return new RegExp(marker, 'i').test(normalizedText); }
                catch (e) { return false; }
            default: return normalizedText.includes(normalizedMarker);
        }
    }
    
    function navigateUp(element, levels) {
        let current = element;
        for (let i = 0; i < levels; i++) {
            current = current.parentElement;
            if (!current) return null;
        }
        return current;
    }
    
    while ((node = walker.nextNode())) {
        const txt = (node.innerText || '').trim();
        if (!txt) continue;
        
        if (isMatch(txt)) {
            let pos = position;
            let upLevels = 0;
            
            // Parse path like 'after/..' or 'after/../..'
            if (typeof position === 'string') {
                const pathMatch = position.match(/^(after|before|sideways)([\/\\]\.\.)+$/);
                if (pathMatch) {
                    pos = pathMatch[1];
                    upLevels = (position.match(/\.\./g) || []).length;
                }
            }
            
            // Navigate up if needed
            let targetNode = node;
            if (upLevels > 0) {
                targetNode = navigateUp(node, upLevels);
                if (!targetNode) return '';
            }
            
            // Handle sideways
            if (pos === 'sideways') {
                let results = [];
                let current = targetNode.parentElement?.firstElementChild;
                
                while (current) {
                    const siblingText = (current.innerText || '').trim();
                    if (siblingText) results.push(siblingText);
                    current = current.nextElementSibling;
                }
                
                if (results.length > 0) return results.join(' ');
                
                let parent = targetNode.parentElement;
                let depth = 1;
                
                while (parent && depth <= 3) {
                    results = [];
                    current = parent.parentElement?.firstElementChild;
                    
                    while (current) {
                        const siblingText = (current.innerText || '').trim();
                        if (siblingText && current !== parent) {
                            results.push(siblingText);
                        }
                        current = current.nextElementSibling;
                    }
                    
                    if (results.length > 0) return results.join(' ');
                    
                    parent = parent.parentElement;
                    depth++;
                }
                
                return '';
            }
            
            // Handle after and before
            let candidate = pos === 'after'
                ? targetNode.nextElementSibling
                : targetNode.previousElementSibling;
            
            if (candidate) {
                const text = (candidate.innerText || '').trim();
                if (text) return text;
            }
            
            candidate = pos === 'after'
                ? targetNode.parentElement?.nextElementSibling
                : targetNode.parentElement?.previousElementSibling;
            
            if (candidate) {
                const text = (candidate.innerText || '').trim();
                if (text) return text;
            }
        }
    }
    
    return '';
}

// works well, returns the start marker and end marker node and their relative path, e.g. identify_node('Throughput', 'Latency', 3);
function identify_node(startMarker, endMarker, search_level = 3) {

    //------------------------------------------------------------
    // Normalize text
    //------------------------------------------------------------
    function normalize(text) {
        return (text || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
    }

    //------------------------------------------------------------
    // Describe element
    //------------------------------------------------------------
    function describe(node) {

        let s = node.tagName.toLowerCase();

        if (node.id)
            s += "#" + node.id;

        if (node.classList.length)
            s += "." + [...node.classList].join(".");

        return s;
    }

    //------------------------------------------------------------
    // Depth
    //------------------------------------------------------------
    function depth(node) {

        let d = 0;

        while (node && node !== document.body) {
            d++;
            node = node.parentElement;
        }

        return d;
    }

    //------------------------------------------------------------
    // Find smallest element containing marker
    //------------------------------------------------------------
    function findSmallest(marker) {

        marker = normalize(marker);

        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_ELEMENT
        );

        let best = null;
        let bestDepth = -1;

        let node;

        while (node = walker.nextNode()) {

            const txt = normalize(node.innerText);

            if (!txt.includes(marker))
                continue;

            const d = depth(node);

            if (d > bestDepth) {
                best = node;
                bestDepth = d;
            }
        }

        return best;
    }

    //------------------------------------------------------------
    // Search subtree
    //------------------------------------------------------------
    function findInSubtree(root, marker, skipNode) {

        marker = normalize(marker);

        const walker = document.createTreeWalker(
            root,
            NodeFilter.SHOW_ELEMENT
        );

        let node;

        while (node = walker.nextNode()) {

            if (node === skipNode)
                continue;

            const txt = normalize(node.innerText);

            if (txt.includes(marker))
                return node;
        }

        return null;
    }

    //------------------------------------------------------------
    // Lowest common ancestor
    //------------------------------------------------------------
    function lca(a, b) {

        const set = new Set();

        while (a) {
            set.add(a);
            a = a.parentElement;
        }

        while (b) {
            if (set.has(b))
                return b;

            b = b.parentElement;
        }

        return null;
    }

    //------------------------------------------------------------
    // Relative path
    //------------------------------------------------------------
    function relativePath(start, end) {

        if (start === end)
            return ".";

        const common = lca(start, end);

        let up = 0;

        let p = start;

        while (p !== common) {
            up++;
            p = p.parentElement;
        }

        const down = [];

        p = end;

        while (p !== common) {
            down.unshift(describe(p));
            p = p.parentElement;
        }

        let path = "";

        for (let i = 0; i < up; i++)
            path += "../";

        path += down.join("/");

        return path || ".";
    }

    //------------------------------------------------------------
    // Relationship
    //------------------------------------------------------------
    function relationship(start, end) {

        if (start === end)
            return "same";

        if (start.parentElement === end.parentElement)
            return "sibling";

        if (start.contains(end))
            return "descendant";

        if (end.contains(start))
            return "ancestor";

        return "sibling_branch";
    }

    //------------------------------------------------------------
    // Find start node
    //------------------------------------------------------------
    const startNode = findSmallest(startMarker);

    if (!startNode) {

        return {
            found:false,
            reason:"start_not_found"
        };
    }

    //------------------------------------------------------------
    // Walk upward
    //------------------------------------------------------------
    let current = startNode;

    for (let level = 0; level <= search_level && current; level++) {

        const endNode =
            findInSubtree(current, endMarker, startNode);

        if (endNode) {

            return {

                found:true,

                ancestor_level:level,

                search_level:search_level,

                relationship:
                    relationship(startNode,endNode),

                relative_path:
                    relativePath(startNode,endNode),

                start:{
                    tag:startNode.tagName.toLowerCase(),
                    text:startNode.innerText.trim(),
                    node:startNode
                },

                end:{
                    tag:endNode.tagName.toLowerCase(),
                    text:endNode.innerText.trim(),
                    node:endNode
                },

                ancestor:{
                    tag:current.tagName.toLowerCase(),
                    node:current
                }
            };
        }

        current = current.parentElement;
    }

    //------------------------------------------------------------
    // Not found
    //------------------------------------------------------------
    return {

        found:false,

        reason:"end_not_found_within_search_level",

        search_level:search_level,

        start:{
            tag:startNode.tagName.toLowerCase(),
            text:startNode.innerText.trim(),
            node:startNode
        }
    };

}

// find the selector string based on marker text
// usage: in devtool console:
generate_selector_for_text('Price') (or your marker).

// It returns an object: 
{ css: '.product-price', xpath: '//*[contains(text(),"Price")]', ... }

// Copy the css string (e.g., '.product-price').
document.querySelector('.product-price')?.innerText.trim();

// In your Playwright script
const price = await page.locator('.product-price').innerText();
// Or using the generated XPath
const price = await page.locator('xpath=//*[contains(text(),"Price")]').innerText();
//

function generate_selector_for_text(marker, matchMode = 'exact') {
    if (typeof marker !== 'string' || marker === '') return null;

    matchMode = String(matchMode || 'exact').toLowerCase();

    const body = document.body;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_ELEMENT);
    let node;

    function isMatch(text) {
        if (!text) return false;
        const normalizedText = text.toLowerCase().trim();
        const normalizedMarker = marker.toLowerCase().trim();

        switch (matchMode) {
            case 'exact': return normalizedText === normalizedMarker;
            case 'contains': return normalizedText.includes(normalizedMarker);
            case 'startswith': return normalizedText.startsWith(normalizedMarker);
            case 'endswith': return normalizedText.endsWith(normalizedMarker);
            case 'regex':
                try { return new RegExp(marker, 'i').test(normalizedText); }
                catch (e) { return false; }
            default: return normalizedText.includes(normalizedMarker);
        }
    }

    while ((node = walker.nextNode())) {
        const txt = (node.innerText || '').trim();
        if (!txt) continue;
        if (isMatch(txt)) {
            // We found the element. Now build a stable selector.
            return buildStableSelector(node);
        }
    }
    return null;
}

function buildStableSelector(element) {
    // 1. If element has an id, use that
    if (element.id) return `#${element.id}`;

    // 2. If it has a data-testid, data-cy, etc.
    const dataAttr = ['data-testid', 'data-cy', 'data-test', 'data-id']
        .find(attr => element.hasAttribute(attr));
    if (dataAttr) {
        const value = element.getAttribute(dataAttr);
        return `[${dataAttr}="${value}"]`;
    }

    // 3. Build a CSS selector using tag and classes
    let selector = element.tagName.toLowerCase();
    if (element.className && typeof element.className === 'string') {
        const classes = element.className.trim().split(/\s+/).filter(c => c);
        if (classes.length > 0) {
            selector += '.' + classes.join('.');
        }
    }

    // 4. If the selector is too generic (e.g., just 'div'), add a parent context
    //    to make it more unique.
    if (selector === 'div' || selector === 'span' || selector === 'p') {
        // Try to include a parent relation
        const parent = element.parentElement;
        if (parent) {
            const parentSelector = buildStableSelector(parent);
            if (parentSelector) {
                selector = `${parentSelector} > ${selector}`;
            }
        }
    }

    // 5. If still too generic, fallback to XPath using the text
    const fullText = element.innerText.trim().substring(0, 30);
    // Escape single quotes for XPath
    const escapedText = fullText.replace(/'/g, "&apos;");
    const xpath = `//*[contains(text(),'${escapedText}')]`;
    // Return the CSS selector, but also provide the XPath as fallback.
    // We'll return an object with both.
    return {
        css: selector,
        xpath: xpath,
        // Also return a combined selector with attribute contains for safety.
        cssWithText: `*:contains("${fullText}")` // not standard CSS, but works with some libraries
    };
}
