"""Quick test: verify service account can access Drive folder."""
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = 'service_account.json'
FOLDER_ID = '1SoD7nzHP8Lfnr8An2NT-SXO-IzJsKkJQ'

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def main():
    print("Authenticating with service account...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    print("[OK] Auth success")

    service = build('drive', 'v3', credentials=creds)

    print(f"\nListing files in folder: {FOLDER_ID}\n")
    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents",
        pageSize=50,
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get('files', [])
    if not files:
        print("No files found. Check folder was shared with service account.")
    else:
        for f in files:
            print(f"  [{f['mimeType'].split('.')[-1]}] {f['name']}  ->  {f['id']}")


if __name__ == '__main__':
    main()
