# 🚨 URGENT: עדכון Google Cloud TTS

## הבעיה הנוכחית:
המערכת עדיין משתמשת ב-gTTS במקום Google Cloud WaveNet.

## הסיבה:
ה-secret `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` מכיל רק את שם הקובץ במקום תוכן ה-JSON.

## פתרון מיידי:

### 1. פתח Replit Secrets
לחץ על המנעול 🔒 בצד שמאל

### 2. מצא את ה-Secret
`GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`

### 3. מחק את התוכן הנוכחי
מחק: `manifest-alpha-465212-r7-bbfa7a03d904.json`

### 4. הדבק את התוכן הזה במלואו:

```json
{
  "type": "service_account",
  "project_id": "manifest-alpha-465212-r7",
  "private_key_id": "673b09e35c9b9d010cef4b1909ad96a42d167683",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEuwIBADANBgkqhkiG9w0BAQEFAASCBKUwggShAgEAAoIBAQCvUQf2xCS4oyNr\nAjla8Cia1DfjRDB9Vl/GJe1JCJV+gPiFHffLWB71xQWWXCTWOvTb2GxDPLrnGW8k\nxggw0Q7/sQaser+w0Rnt20C1C66roj1t9FAMGyMUrEUPpwPHXt9se2PJ/V+netso\nH/+aVESupTF5HAgM1lM7c6LOpbXKtdFgF3ookYJb/GMxdL4uQbuFHwciycXbp4Pd\nVU24sdDB2qhYUUJGW7YglGcaA/I+SGzAnIHl1fepaWE/zt0cK5qd7BoyswS+kJNy\n3UNHg5DYqSNLSOJfYdNaNl0S7+c2d/hODUX98iCW2sTlsZgTnmnvDD8ij8Wit58c\nCbeqb4BxAgMBAAECgf9Ya/C2M9lReaESW8zNcvUp7qNBZ0li3LG+IJ6ZqnIiJCXe\nl1yjA47eKlo8ZmeUPrkV9Wtx5GbXUpqEbUu8ysU5BiVTR5WinKCmMC7/ZUceQSBL\ng5O5uo+28tad1ucVRNm3ri6qgqSEccvsUwQCPSBV0yYLUVgCVLA3C/2d7zG85Erq\neaCxz3Vl2uHCSb7lw2yiVY8Yn7lSJxxrc+Ws6A9CtRDjIQiJUPL4hqCA9dvMzzmi\nMnUXEP7pu6EdGAMpTDGIF4B4XSXPGoe4IFneNWovgB0WMmKVNDhpEO0J7QMMUi2R\n5AzOBOWOjVnkCRJFOG8K34YabBHGjNZT5zs0WQECgYEA5+7+OHxIehQHJQWSO+ln\ncv1OEV0qpH2XTrZAKtibH2cxnd8RAuXqqecX8biL5SHOhxSRqRQacDVXAUwQe19S\n0PUtlhg7vgpMSpbi9TOrDJ8Bfdit0xgzDX5KGTLkh0/0pbJLHhYZqg9qTjU2cOH3\nptrm3sWIRlD1hJ+kli9a3rECgYEAwYIU6D9CnYd6BmWTMQouAlkKX30nmX8Wp3oY\n+A8rrEwnL/Ulko221ajuPK7JUUupZio6+nwIWpYErR59uif1hwPx1bNu8kt6bxSB\nQPhEV/TTKxMEyy31PDKo8kb57OwZMj4J0v0WrxVvp5wvW1PWEwWomVjOts525ozF\ncHFwrcECgYAww3PZxm+qkxlpdEFprUodyBoo1nDHwswUNYdKOt5qfNTWv3ahKFvt\nOvQy0z0+gJwelHmHlf11CBHx6N8yQTl1S4c5HoE5FIszx4OSUDmvXqL+pZbuYhEh\nziKgJ64asPnb+J+IhNcChVkxdkiq9SePgki2H8vmFNF5/+Kn3O77EQKBgAt2Uxq2\ntJF0NuwuFBvxiGwnLhAd77yN5J+jAdufumyITkHu+XzG3C+nxATgLZidLLmagsfX\nlP8Yp8pBZh0ixM5sk2SfLlE321a9FjLtAc9b9y40ADKw1DfuoEdJoQBBs/Rf7GEN\nEMzqLiT1gXCddK7HxQbgVc5KSIy7he51KcGBAoGBAKtPppJHaZvSebUOA/puZGP5\nhErhxp3aozl1RvHtO2R10B1kP+k4JwTNQaPBtVscwsbWJ+1FCY8H+QJnar6Nyo+D\nAW0FaWXg8Mk4P/WzIXHIfnY8JPyS+4wLfFIKFkd7whJCnUyJozDy1tFWUJzAcE1v\n8xVMhUdvvHeInOq02O6G\n-----END PRIVATE KEY-----\n",
  "client_email": "tts-service@manifest-alpha-465212-r7.iam.gserviceaccount.com",
  "client_id": "116081385664114981196",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/tts-service%40manifest-alpha-465212-r7.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
```

### 5. שמור
המערכת תתאחל אוטומטית.

### 6. זיהוי הצלחה
אחרי העדכון תראה בלוגים:
```
✅ Google Cloud TTS Client initialized successfully!
✅ Found Hebrew WaveNet voices
✅ WaveNet synthesis successful
```

## תוצאה סופית:
קול עברי איכותי מ-Google Cloud WaveNet במקום gTTS!