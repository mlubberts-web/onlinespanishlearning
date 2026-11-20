# Putting the app online

This makes the app a website that anyone you give a login can open in a browser, on any computer,
with nothing to install. Each person has their own results. It costs nothing; you need three free
accounts: GitHub (where the code is), Supabase (a database for the results) and Streamlit
Community Cloud (which runs the app).

Why a database: the online server forgets its files whenever it restarts, which happens often, so
progress.json, practice.json and study_log.json can't live there. On your own computer nothing
changes: without the secrets below, the app keeps using those files and doesn't ask for a login.

## 1. The database (Supabase)

1. Make an account at [supabase.com](https://supabase.com). A new account first asks you to create
   an **organization** (the folder your projects live in): any name, type **Personal**, plan
   **Free**. Then click **New project** inside it. Any name and
   database password will do (you won't need that password again). As the region, pick one in the
   US East, close to Streamlit's servers, so saving is quick.
2. When the project is ready, open **SQL Editor** in the left menu, paste this and click **Run**:

   ```sql
   create table saves (
     owner text not null,           -- whose results: the name you log in with
     name text not null,            -- which file: progress, practice or study_log
     data jsonb not null,           -- the contents of that file
     primary key (owner, name)
   );
   -- Nobody can read the table from a browser; only the app's server can, with the secret key.
   alter table saves enable row level security;
   -- Give the secret key access to this table (needed when "Grant API access to new tables
   -- automatically" was left off while creating the project).
   grant select, insert, update, delete on table saves to service_role;
   ```

   While creating the project, keep **Enable Data API** ticked; the other two boxes under
   "Data access" can stay as they are.

3. Open **Project Settings** (the gear at the bottom left), then **API Keys**. Copy the
   **secret key** (it starts with `sb_secret_`; click the eye or copy icon to see it). If the page
   only offers **Create new API keys**, click that first. The older **service_role** key on the
   "Legacy" tab works too.

   The **Project URL** looks like `https://abcdefgh.supabase.co`. You can find it with the
   **Connect** button at the top of the project, or build it yourself: the browser's address bar
   shows `supabase.com/dashboard/project/abcdefgh`, and `abcdefgh` is the part you need.

Keep the secret key to yourself: whoever has it can read and change all results.

A free Supabase project is paused after a week without any use. If you both stop for a while,
log in to Supabase and click **Restore project**; nothing is lost.

## 2. The code (GitHub)

The code has to be in a GitHub repository. Your own results and the secrets are never uploaded:
`.gitignore` leaves them out.

## 3. The app (Streamlit Community Cloud)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **Create app**, then **Deploy a public app from GitHub**, and fill in:
   - Repository: your repository
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: a name you like, for example `spanish-study`
3. Open **Advanced settings**. Choose Python **3.12**, and paste this into **Secrets**, with your
   own values:

   ```toml
   [supabase]
   url = "https://abcdefgh.supabase.co"
   key = "sb_secret_..."

   [users.menno]
   password = "think of a long password"
   timezone = "Europe/Amsterdam"

   [users.ana]
   password = "another long password"
   timezone = "Europe/Madrid"
   ```

   Each `[users.<name>]` part is one person, who logs in with that name (in small letters, no
   spaces) and password. The time zone decides when a new day starts for that person; find yours
   in the "TZ identifier" column of
   [this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
4. Click **Deploy**. The first start takes a few minutes.

To add a person or change a password later: in Streamlit Community Cloud, open the app's
**Settings**, then **Secrets**.

## 4. Using it

- Open the app's address and log in. The address then gets a `?login=...` part: bookmark that
  page, and next time the app logs you in by itself. Don't share the bookmark; it works like a
  password. Changing the password makes old bookmarks stop working.
- **Your results from your own computer:** in the sidebar, open **💾 Your data**, choose
  `progress.json`, `practice.json` and `study_log.json` from the app folder, and click
  **Replace my results**. Then keep using the online version, because the two don't stay in step.
- **Backups:** **💾 Your data** also has **Download a backup**. Putting a backup back works the
  same way as above.
- An app that nobody opened for a while goes to sleep. Opening it shows a button to wake it up,
  which takes about a minute.
- After you upload a change to GitHub, the online app updates itself within a few minutes.
