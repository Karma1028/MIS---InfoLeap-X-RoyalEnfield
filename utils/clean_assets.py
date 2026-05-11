import os

def clean_assets(directory):
    files = os.listdir(directory)
    deleted_count = 0
    for filename in files:
        if filename.endswith(".jpg"):
            filepath = os.path.join(directory, filename)
            is_invalid = False
            
            # Check size
            if os.path.getsize(filepath) < 50 * 1024:
                is_invalid = True
                reason = "Size < 50KB"
            else:
                # Check for HTML header
                try:
                    with open(filepath, 'rb') as f:
                        header = f.read(100)
                        if b'<!DOCTYPE' in header or b'<html' in header:
                            is_invalid = True
                            reason = "HTML detected"
                except:
                    pass
            
            if is_invalid:
                print(f"Deleting {filename} ({reason})")
                os.remove(filepath)
                deleted_count += 1
    
    print(f"Cleaned up {deleted_count} invalid asset(s).")

if __name__ == "__main__":
    clean_assets(r"D:\antigravity project\infoleap project\royal enfield\assets\bikes")
