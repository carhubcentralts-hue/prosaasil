#!/usr/bin/env python
# קובץ הפעלה יציב לאפליקציה
import os
import sys
import time
import subprocess

def start_server():
    print("🚀 מפעיל שרת AgentLocator...")
    
    # נוודא שאנחנו בתיקייה הנכונה
    os.chdir('server')
    
    # מפעיל את השרת
    try:
        os.system('python app.py')
    except KeyboardInterrupt:
        print("\n⏹️ עוצר שרת...")
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        time.sleep(2)
        start_server()  # מנסה שוב

if __name__ == "__main__":
    start_server()