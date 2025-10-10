import requests

url = "http://127.0.0.1:5000/find_matches"
payload = {"cargo_id": 37}  # a mentett Cargo ID
response = requests.post(url, json=payload)

print(response.status_code)
print(response.json())
