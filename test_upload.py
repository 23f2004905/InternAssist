import requests

url = "http://127.0.0.1:5001/api/auth/login"

login_data = {
    "email": "admin@internassist.edu",
    "password": "Admin@12345"
}

session = requests.Session()

response = session.post(url, json=login_data)
print("Login status:", response.status_code)

if response.status_code != 200:
    print(response.text)
    exit()

with open("test_files/sample.pdf", "rb") as file:
    response = session.post(
        "http://127.0.0.1:5001/api/documents",
        data={"title": "PDF Test"},
        files={"file": ("sample.pdf", file, "application/pdf")}
    )

print("Upload status:", response.status_code)
print("Response body:", response.text[:2000])