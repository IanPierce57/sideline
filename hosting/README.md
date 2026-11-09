# Putting Sideline online

Sideline is a Python server plus a webpage, so to use it from anywhere it has to run on a server. It runs on **Google Cloud Run**, in the same Google Cloud account as the voices. Cloud Run builds it from the [Dockerfile](../Dockerfile) at the top of this repo, and shuts it down when nobody is using it, so a few test segments fit in Google's free monthly allowance.

## How the online copy is protected

Every new segment costs about 60 cents in Claude API credits, so the online copy has limits that the version on your own computer doesn't:

- **Access code:** making a new segment needs the access code. Replaying a saved segment (**Last segment**) works for anyone and costs nothing.
- **15 new segments a day**, and **one at a time**. Questions the call screener turns away don't count.
- The keys are stored in the Cloud Run service's settings. They never go in this repo.

## Setting it up (about 10 minutes)

You need the Google Cloud project with billing that you use for the Sideline voices, and your keys. It's best to make a new Claude key just for the website at [console.anthropic.com](https://console.anthropic.com) → **API Keys**, so you can delete it after grading.

1. Open [console.cloud.google.com](https://console.cloud.google.com) and pick your Sideline project at the top.
2. Click the **>_** button at the top right (**Activate Cloud Shell**). A terminal opens at the bottom of the page.
3. Paste this line into it and press Return:

   ```bash
   git clone https://github.com/IanPierce57/sideline.git && sideline/hosting/deploy-cloud-run.sh
   ```

4. When it asks for your keys, open your `.env` file in TextEdit (`open -e .env` in the project folder on your Mac), press **Cmd+A** and **Cmd+C**, click back in the Cloud Shell terminal, press **Cmd+V**, then **Return**. The keys don't show on screen. It checks that they work and makes up an access code. If Cloud Shell asks to **Authorize**, click it.
5. Wait about 5 minutes. At the end it prints the link (something like `https://sideline-....run.app`) and the access code to give your professor.

To update the online copy after changing the code, push to GitHub, then in Cloud Shell run:

```bash
cd ~/sideline && git pull && hosting/deploy-cloud-run.sh
```

## Good to know

- **The first visit after a quiet spell** takes a few extra seconds while it starts, and the first segment can take a minute longer while it downloads the sports data.
- **Segments made online stay online.** They're saved inside the server (the newest 10) and are gone when it shuts down. The 10 saved segments in this repo are always there.
- **Taking it offline:** in Cloud Shell, run `gcloud run services delete sideline --region us-east1`, then delete the Claude key you made for it.
