import requests
import sys
import json
from datetime import datetime

class RestaurantAPITester:
    def __init__(self, base_url="https://lacongolaise-web.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {name}")
        if details:
            print(f"   Details: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, check_response=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            
            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if success and check_response:
                try:
                    response_data = response.json()
                    check_result = check_response(response_data)
                    if not check_result[0]:
                        success = False
                        details += f", Response check failed: {check_result[1]}"
                    else:
                        details += f", Response: {check_result[1]}"
                except Exception as e:
                    success = False
                    details += f", Response parsing error: {str(e)}"
            
            if not success and response.status_code != expected_status:
                try:
                    error_data = response.json()
                    details += f", Error: {error_data}"
                except:
                    details += f", Raw response: {response.text[:200]}"
            
            self.log_test(name, success, details)
            return success, response.json() if success else {}

        except requests.exceptions.RequestException as e:
            self.log_test(name, False, f"Request error: {str(e)}")
            return False, {}
        except Exception as e:
            self.log_test(name, False, f"Unexpected error: {str(e)}")
            return False, {}

    def test_api_root(self):
        """Test API root endpoint"""
        def check_root_response(data):
            if "message" in data and "La Congolaise" in data["message"]:
                return True, f"Message: {data['message']}"
            return False, f"Unexpected response format: {data}"
        
        return self.run_test(
            "API Root",
            "GET",
            "api/",
            200,
            check_response=check_root_response
        )

    def test_get_initial_stats(self):
        """Test getting initial review stats"""
        def check_stats_response(data):
            required_fields = ["average_rating", "total_reviews"]
            for field in required_fields:
                if field not in data:
                    return False, f"Missing field: {field}"
            
            if not isinstance(data["average_rating"], (int, float)):
                return False, f"Invalid average_rating type: {type(data['average_rating'])}"
            
            if not isinstance(data["total_reviews"], int):
                return False, f"Invalid total_reviews type: {type(data['total_reviews'])}"
            
            return True, f"Average: {data['average_rating']}, Total: {data['total_reviews']}"
        
        return self.run_test(
            "Get Initial Stats",
            "GET",
            "api/reviews/stats",
            200,
            check_response=check_stats_response
        )

    def test_get_initial_reviews(self):
        """Test getting initial reviews list"""
        def check_reviews_response(data):
            if not isinstance(data, list):
                return False, f"Expected list, got {type(data)}"
            return True, f"Found {len(data)} reviews"
        
        return self.run_test(
            "Get Initial Reviews",
            "GET",
            "api/reviews",
            200,
            check_response=check_reviews_response
        )

    def test_create_review(self, name, rating, comment=None):
        """Test creating a review"""
        review_data = {
            "name": name,
            "rating": rating
        }
        if comment:
            review_data["comment"] = comment
        
        def check_create_response(data):
            required_fields = ["id", "name", "rating", "created_at"]
            for field in required_fields:
                if field not in data:
                    return False, f"Missing field: {field}"
            
            if data["name"] != name:
                return False, f"Name mismatch: expected {name}, got {data['name']}"
            
            if data["rating"] != rating:
                return False, f"Rating mismatch: expected {rating}, got {data['rating']}"
            
            if comment and data.get("comment") != comment:
                return False, f"Comment mismatch: expected {comment}, got {data.get('comment')}"
            
            return True, f"Created review ID: {data['id']}"
        
        success, response = self.run_test(
            f"Create Review ({name}, {rating} stars)",
            "POST",
            "api/reviews",
            200,
            data=review_data,
            check_response=check_create_response
        )
        
        return success, response.get("id") if success else None

    def test_reviews_sorting(self):
        """Test different sorting options"""
        sort_options = [
            ("date_desc", "Most Recent"),
            ("date_asc", "Oldest"),
            ("rating_desc", "Highest Rated"),
            ("rating_asc", "Lowest Rated")
        ]
        
        all_passed = True
        for sort_value, sort_name in sort_options:
            def check_sort_response(data):
                if not isinstance(data, list):
                    return False, f"Expected list, got {type(data)}"
                return True, f"Sorted by {sort_name}: {len(data)} reviews"
            
            success, _ = self.run_test(
                f"Sort Reviews - {sort_name}",
                "GET",
                f"api/reviews?sort={sort_value}",
                200,
                check_response=check_sort_response
            )
            if not success:
                all_passed = False
        
        return all_passed

    def test_invalid_review_data(self):
        """Test validation with invalid data"""
        test_cases = [
            ({"name": "", "rating": 3}, "Empty name"),
            ({"name": "Test", "rating": 0}, "Rating too low"),
            ({"name": "Test", "rating": 6}, "Rating too high"),
            ({"rating": 3}, "Missing name"),
            ({"name": "Test"}, "Missing rating"),
        ]
        
        all_passed = True
        for invalid_data, description in test_cases:
            success, _ = self.run_test(
                f"Invalid Data - {description}",
                "POST",
                "api/reviews",
                422,  # Validation error
                data=invalid_data
            )
            if not success:
                all_passed = False
        
        return all_passed

def main():
    print("🧪 Starting La Congolaise Restaurant API Tests")
    print("=" * 50)
    
    tester = RestaurantAPITester()
    
    # Test API connectivity
    print("\n📡 Testing API Connectivity...")
    if not tester.test_api_root()[0]:
        print("❌ API root test failed - stopping tests")
        return 1
    
    # Test initial state
    print("\n📊 Testing Initial State...")
    tester.test_get_initial_stats()
    tester.test_get_initial_reviews()
    
    # Test review creation
    print("\n📝 Testing Review Creation...")
    test_reviews = [
        ("Marie Dubois", 5, "Excellent cuisine congolaise! Le poulet moambé était délicieux."),
        ("John Smith", 4, "Great authentic flavors, friendly service."),
        ("Pierre Martin", 3, None),  # No comment
        ("Sarah Johnson", 5, "Amazing food and atmosphere!"),
        ("Antoine Leroy", 2, "Service was slow but food was okay."),
    ]
    
    created_reviews = []
    for name, rating, comment in test_reviews:
        success, review_id = tester.test_create_review(name, rating, comment)
        if success and review_id:
            created_reviews.append(review_id)
    
    # Test stats after creating reviews
    print("\n📈 Testing Updated Stats...")
    tester.test_get_initial_stats()
    
    # Test sorting functionality
    print("\n🔄 Testing Review Sorting...")
    tester.test_reviews_sorting()
    
    # Test validation
    print("\n🛡️ Testing Data Validation...")
    tester.test_invalid_review_data()
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️ {tester.tests_run - tester.tests_passed} tests failed")
        
        # Show failed tests
        failed_tests = [t for t in tester.test_results if not t["success"]]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())