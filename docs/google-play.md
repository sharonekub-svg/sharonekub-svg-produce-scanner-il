# העלאה ל-Google Play – מדריך צעד אחרי צעד

קבצים (נשלחו בצ'אט; הגרפיקה נבנית מחדש עם `scanfruit-store` – ראו למטה):
- `app-release.aab` – האפליקציה, גרסה 1.5.0 (versionCode 6), חתומה במפתח ההעלאה.
- `scanfruit-upload.keystore` + `upload-key-README.txt` – מפתח ההעלאה והסיסמה. **לשמור בצד, לא בריפו.** כל עדכון עתידי נחתם בו.
- `icon-512.png`, `feature-graphic-1024x500.png`, `screenshot-01..05.png` (1080×1920).
- מדיניות פרטיות: https://sharonekub-svg-produce-scanner-il.vercel.app/privacy

בניית AAB לעדכון הבא: `UPLOAD_KEYSTORE=... UPLOAD_PASSWORD=... scripts/build_android_aab.sh` (להעלות קודם את `versionCode` ב-`app/app.json`).

## 1. יצירת האפליקציה ב-Play Console
1. play.google.com/console → **Create app**.
2. App name: `Scan Fruit AI – סורק פירות` · Default language: **Hebrew – iw-IL** · App · **Free**.
3. לסמן את שתי ההצהרות (Developer Program Policies, US export laws) → **Create app**.

## 2. Store listing (Grow → Store presence → Main store listing)
**App name (עד 30):** `Scan Fruit AI – סורק פירות`

**Short description (עד 80):**
`מצלמים פרי או ירק ומקבלים ציון 1–10, שלב בשלות וטיפ אחסון – בחינם.`

**Full description:**
```
לא בטוחים אם הפרי בסופר טוב? מצלמים אותו – ותוך שניות יודעים.

Scan Fruit AI בודקת פירות וירקות מתוך תמונה:
⭐ ציון מ-1 עד 10 – כמה הפרי טוב עכשיו
🍌 שלב בשלות וטריות – בשל, כמעט בשל, בשל מדי, סימני קלקול
💡 טיפ אחסון ומה לבדוק ביד – לכל סוג
📷 לא בטוחים? האפליקציה תבקש זווית נוספת ותשלב את שתי התמונות
🕘 "הסריקות שלי" – כל סריקה נשמרת, ואפשר להתחבר עם Google כדי לראות אותן מכל מכשיר

מזהה עשרות סוגים: תפוח, בננה, תפוז, לימון, אבוקדו, מנגו, תות, ענבים, רימון, עגבנייה, מלפפון, פלפל, אבטיח, אננס, גזר, ברוקולי, פטריות ועוד.

✅ בחינם · בלי פרסומות · בלי הרשמה
🔒 התמונה נשלחת לניתוח ולא נשמרת

חשוב: זו הערכה חזותית בלבד ואינה מבטיחה שהמזון בטוח לאכילה.
```
- App icon: `icon-512.png` · Feature graphic: `feature-graphic-1024x500.png` · Phone screenshots: `screenshot-01..05.png`.
- Category: **Food & Drink** · Contact email: המייל שלך · Website: כתובת האתר.

## 3. App content (Policy → App content) – התשובות
| טופס | תשובה |
|---|---|
| Privacy policy | `https://sharonekub-svg-produce-scanner-il.vercel.app/privacy` |
| App access | All functionality is available without special access |
| Ads | No, my app does not contain ads |
| Content rating | שאלון IARC: Category **Utility / Productivity / Communication / Other**; לכל שאלות האלימות, מין, שפה, הימורים, סמים – **No**; האם משתמשים מתקשרים זה עם זה / משתפים תוכן – **No**; מיקום – **No** → יוצא **Everyone / 3+** |
| Target audience | **18 and over** (פשוט יותר: לא חל עליו מסלול Families) |
| News app | No |
| Data safety | ראו למטה |
| Government app / Financial features / Health | No / None / No |

### Data safety
- Does your app collect or share any of the required user data types? **Yes**
- Is all user data encrypted in transit? **Yes**
- Account creation: **OAuth** (Google) · Delete account / Delete data URL: `https://sharonekub-svg-produce-scanner-il.vercel.app/privacy#delete` · retention: **No** (נמחק מיד לפי בקשה)
- Do you provide a way for users to request deletion? **Yes** (מחיקת חשבון באפליקציה + מייל)

| סוג נתון | נאסף? | משותף? | ephemeral | חובה/רשות | מטרה |
|---|---|---|---|---|---|
| Photos and videos → **Photos** | Yes | No | **No** (הניתוח עצמו לא נשמר, אבל תמונה מוקטנת נשמרת בחשבון/בשיתוף לאימון) | Required | App functionality |
| Personal info → **Name**, **Email address** | Yes | No | No | **Optional** (רק בהתחברות עם Google) | App functionality, Account management |
| App activity → **Other user-generated content** (תוצאות סריקה + תמונה מוקטנת בחשבון) | Yes | No | No | Optional | App functionality |
| App activity → **Other actions** (👍/👎, סקר) | Yes | No | No | Optional | Analytics |

"Shared" = No: Vercel, Supabase ו-Google הם ספקי שירות שפועלים בשמנו, וזה לא נחשב שיתוף.

## 4. בדיקה סגורה (חובה בחשבון אישי חדש: 12 בודקים × 14 יום)
1. Test and release → Testing → **Closed testing** → Create track (או Alpha).
2. **Testers**: Create email list → להוסיף לפחות 12 כתובות Gmail (חברים ומשפחה) → Save.
3. **Create new release** → Play App Signing: **Continue** (גוגל מנהלת את מפתח החתימה) → להעלות `app-release.aab`.
4. Release name: `1.5.0` · Release notes (iw-IL): `גרסה ראשונה: זיהוי פירות וירקות, ציון 1–10, טיפים, הסריקות שלי.`
5. Next → **Save and publish** → Send for review (בדרך כלל 1–3 ימים).
6. אחרי האישור: להעתיק את **Join on the web** link ולשלוח לבודקים. כל אחד לוחץ "Become a tester" ומתקין מ-Play. הם צריכים להישאר רשומים 14 יום ולהשתמש באפליקציה.
7. אחרי 14 יום: Dashboard → **Apply for production** → שאלון קצר על הבדיקה → אחרי אישור – Production release עם אותו AAB.

## 5. דברים שכדאי לדעת
- ההתחברות עם Google עוברת דרך הדפדפן (Supabase), ולכן לא צריך לרשום את טביעת האצבע של מפתח החתימה ב-Google Cloud.
- כל עדכון: להעלות `versionCode` ב-1, לבנות AAB חדש עם אותו keystore, Create new release באותו track.
