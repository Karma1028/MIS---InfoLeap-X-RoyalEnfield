import os
from supabase import create_client, Client

url = "https://xcnguusutacgqwqlmjvu.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhjbmd1dXN1dGFjZ3F3cWxtanZ1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDUyMDQ2MSwiZXhwIjoyMDkwMDk2NDYxfQ.OEeGmrr3B3uF_By1mwHCA0nIFlqA4HR7ut7wvHJSX2M"
supabase: Client = create_client(url, key)

def check_schema():
    print("Checking Supabase tasks table schema...")
    try:
        response = supabase.table("tasks").select("*").limit(1).execute()
        if response.data:
            print("Columns in 'tasks' table:")
            print(list(response.data[0].keys()))
            
            # Now search again with the right columns
            # Assuming 'task' or 'title' or 'context'
            matches = [t for t in response.data if 'infoleap' in str(t).lower() or 'royalenfield' in str(t).lower()]
            if matches:
                 print("Found matches in initial sample.")
        else:
            print("Tasks table is empty.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
