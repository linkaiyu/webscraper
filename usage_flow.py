# ===== FRONTEND CLIENT =====
class AuthoringClient:
    """Client for interacting with the authoring tool"""
    
    def __init__(self, server_url="http://localhost:8000"):
        self.server_url = server_url
    
    def author_scraper(self, url: str, intent: str) -> Dict:
        """
        Author a new scraper for a website
        """
        response = requests.post(
            f"{self.server_url}/author",
            json={"url": url, "intent": intent}
        )
        return response.json()
    
    def test_workflow(self, workflow_id: str) -> Dict:
        """Test a captured workflow"""
        response = requests.post(
            f"{self.server_url}/test/{workflow_id}"
        )
        return response.json()

# ===== USER INTERACTION EXAMPLE =====
def main():
    client = AuthoringClient()
    
    # User: "I want to scrape products from this electronics store"
    result = client.author_scraper(
        url="https://example-electronics.com/products",
        intent="Extract all products with name, price, and specifications. Navigate through all pages and for each product, go to detail page to get full specs."
    )
    
    print("✅ Workflow generated!")
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Configuration saved to: workflow_{result['workflow_id']}.json")
    print(f"Code generated: scraper_{result['workflow_id']}.py")
    
    # The generated code can be run anytime:
    # python scraper_123456.py
    
if __name__ == "__main__":
    main()