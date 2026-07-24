// from DeepSeek, support get_nearby_text('marker', 'after/..' | 'before/..')
// 'contains' | 'startswith' | 'endswith'

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
