import os
from supabase import create_client, Client

url = "https://xcnguusutacgqwqlmjvu.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhjbmd1dXN1dGFjZ3F3cWxtanZ1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDUyMDQ2MSwiZXhwIjoyMDkwMDk2NDYxfQ.OEeGmrr3B3uF_By1mwHCA0nIFlqA4HR7ut7wvHJSX2M"
supabase: Client = create_client(url, key)

def query_supabase():
    print("Querying Supabase for 'infoleap' or 'RoyalEnfield'...")
    
    # Check tasks table
    try:
        response = supabase.table("tasks").select("*").or_("context.eq.infoleap,description.ilike.%RoyalEnfield%,title.ilike.%RoyalEnfield%").execute()
        if response.data:
            print(f"Found {len(response.data)} matching tasks:")
            for task in response.data:
                print(f"--- Task {task.get('id')} ---")
                print(f"Title: {task.get('title')}")
                print(f"Description: {task.get('description')}")
                print(f"Context: {task.get('context')}")
        else:
            print("No matching tasks found.")
    except Exception as e:
        print(f"Error querying tasks: {e}")

    # Check hot_memory table (if it exists, based on AGENTS.md)
    try:
        response = supabase.table("hot_memory").select("*").or_("content.ilike.%gdnindia%,content.ilike.%RoyalEnfield%,content.ilike.%infoleap%").execute()
        if response.data:
            print(f"Found {len(response.data)} matching memory entries:")
            for mem in response.data:
                print(f"--- Memory {mem.get('id')} ---")
                print(f"Content: {mem.get('content')}")
        else:
            print("No matching memory entries found.")
    except Exception as e:
        print(f"Error querying hot_memory: {e}")

if __name__ == "__main__":
    query_supabase()
