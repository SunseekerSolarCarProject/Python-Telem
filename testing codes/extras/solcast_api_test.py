import requests
import json
from datetime import datetime
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

def get_solcast_data_query(api_key, rooftop_site_id):
    """
    Fetches estimated actuals using Query String authentication.
    """
    url = f"https://api.solcast.com.au/rooftop_sites/{rooftop_site_id}/estimated_actuals"
    params = {
        'format': 'json',
        'api_key': api_key  # API key in query string
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"[Query String] HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"[Query String] An error occurred: {err}")
    return None

def get_solcast_data_bearer(api_key, rooftop_site_id):
    """
    Fetches estimated actuals using Bearer Token authentication.
    """
    url = f"https://api.solcast.com.au/rooftop_sites/{rooftop_site_id}/estimated_actuals"
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    params = {
        'format': 'json'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"[Bearer Token] HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"[Bearer Token] An error occurred: {err}")
    return None

def get_solcast_data_basic(api_key, rooftop_site_id):
    """
    Fetches estimated actuals using Basic Authentication.
    """
    url = f"https://api.solcast.com.au/rooftop_sites/{rooftop_site_id}/estimated_actuals"
    auth = HTTPBasicAuth(api_key, '')  # API key as username, empty password
    params = {
        'format': 'json'
    }
    
    try:
        response = requests.get(url, auth=auth, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"[Basic Auth] HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"[Basic Auth] An error occurred: {err}")
    return None

def get_solcast_data_digest(api_key, rooftop_site_id):
    """
    Fetches estimated actuals using Digest Authentication.
    """
    url = f"https://api.solcast.com.au/rooftop_sites/{rooftop_site_id}/estimated_actuals"
    auth = HTTPDigestAuth(api_key, '')  # API key as username, empty password
    params = {
        'format': 'json'
    }
    
    try:
        response = requests.get(url, auth=auth, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"[Digest Auth] HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"[Digest Auth] An error occurred: {err}")
    return None

def save_data_to_file(data, filename):
    """
    Saves the fetched data to a text file in a readable format.
    """
    try:
        with open(filename, 'w') as file:
            file.write("Solcast Estimated Actuals Data\n")
            file.write(f"Fetched on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if 'estimated_actuals' in data:
                file.write("PV Estimates:\n")
                file.write("-----------------\n")
                for estimate in data['estimated_actuals']:
                    period_end = estimate.get('period_end', 'N/A')
                    pv_estimate = estimate.get('pv_estimate', 'N/A')
                    period = estimate.get('period', 'N/A')
                    file.write(f"Time: {period_end}, PV Estimate: {pv_estimate} kW, Period: {period}\n")
            else:
                file.write("No estimated actuals data available.\n")
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"Failed to save data to file: {e}")

def select_auth_method():
    """
    Prompts the user to select an authentication method.
    """
    print("\nSelect Authentication Method:")
    print("1. Query String")
    print("2. Bearer Token")
    print("3. Basic Authentication")
    print("4. Digest Authentication")
    choice = input("Enter the number corresponding to your choice (1-4): ").strip()
    return choice

def main():
    """
    Main function to execute the script.
    """
    print("=== Solcast Estimated Actuals Fetcher ===\n")
    
    # Replace 'YOUR_SOLCAST_API_KEY' with your actual Solcast API key or prompt the user
    # Optionally, for better security, you can use environment variables or input prompts
    api_key = input("Enter your Solcast API Key: ").strip()
    
    # Get user input for rooftop site ID
    rooftop_site_id = input("Enter your Rooftop Site ID (e.g., 272a-4117-baac-52a0): ").strip()
    
    if not api_key or not rooftop_site_id:
        print("API Key and Rooftop Site ID are required.")
        return
    
    # Select authentication method
    choice = select_auth_method()
    
    # Fetch data based on selected method
    data = None
    if choice == '1':
        data = get_solcast_data_query(api_key, rooftop_site_id)
    elif choice == '2':
        data = get_solcast_data_bearer(api_key, rooftop_site_id)
    elif choice == '3':
        data = get_solcast_data_basic(api_key, rooftop_site_id)
    elif choice == '4':
        data = get_solcast_data_digest(api_key, rooftop_site_id)
    else:
        print("Invalid choice. Please select a number between 1 and 4.")
        return
    
    if data:
        # Define the output filename with timestamp
        filename = f"solcast_estimated_actuals_{rooftop_site_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        # Save data to file
        save_data_to_file(data, filename)
    else:
        print("No data fetched from Solcast API.")

if __name__ == "__main__":
    main()
