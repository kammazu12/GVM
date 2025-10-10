import requests

API_KEY = '8beea4482c34ee86ba00302f7d240d0b'
HEADERS = {
    'x-apisports-key': API_KEY
}

# 2022-es PL 10. forduló dátumtartománya
start_date = '2022-10-08'
end_date = '2022-10-10'

url = 'https://v3.football.api-sports.io/fixtures'
params = {
    'league': 39,      # Premier League
    'season': 2023,
    'from': start_date,
    'to': end_date,
    'status': 'FT'     # Csak befejezett meccsek
}

response = requests.get(url, headers=HEADERS, params=params)
data = response.json()

# Kiírás
print(f"\nPremier League 2022 – 10. forduló ({start_date} - {end_date}):\n")
if data.get('response'):
    for match in data['response']:
        fixture = match['fixture']
        teams = match['teams']
        goals = match['goals']
        date = fixture['date'][:10]
        print(f"{date}: {teams['home']['name']} {goals['home']} - {goals['away']} {teams['away']['name']}")
else:
    print("Nincs elérhető meccsadat ebben az időszakban.")