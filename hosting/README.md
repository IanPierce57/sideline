# Putting Sideline online

Sideline is a Python server plus a webpage, so to use it from anywhere it has to run on a server. It's hosted for free on **Hugging Face Spaces**: the Space builds from the [Dockerfile](Dockerfile) in this folder, which pulls the code from this GitHub repo.

## How the hosted copy is protected

Every new segment costs about 60 cents in Claude API credits, so the hosted copy has limits that the version on your own computer doesn't:

- **Access code:** making a new segment needs the access code. Replaying a saved segment (**Last segment**) works for anyone and costs nothing.
- **15 new segments a day**, and **one at a time**. Questions the call screener turns away don't count.
- The keys are stored as private **secrets** in the Space's settings. They never go in this repo.

To change the limits, add a Space variable named `SIDELINE_DAILY_LIMIT` or `SIDELINE_MAX_AT_ONCE`.

## Setting it up (about 10 minutes)

1. **Make a free account** at [huggingface.co/join](https://huggingface.co/join) and confirm your email.
2. **Create the Space:** go to [huggingface.co/new-space](https://huggingface.co/new-space).
   - Space name: `sideline`
   - SDK: **Docker**, template **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public**
   - Click **Create Space**.
3. **Add the Dockerfile:** in the new Space, open the **Files** tab, click **+ Add file → Create a new file**, name it `Dockerfile`, paste in everything from [Dockerfile](Dockerfile), and click **Commit new file to main**.
4. **Add the secrets:** open **Settings**, scroll to **Variables and secrets**, and click **New secret** for each of these:

   | Name | Value |
   | --- | --- |
   | `ANTHROPIC_API_KEY` | A Claude API key. It's best to make a new one just for the website at [console.anthropic.com](https://console.anthropic.com) → **API Keys**, so you can delete it after grading. |
   | `GOOGLE_TTS_KEY` | The Google Cloud Text-to-Speech key (for the voices). |
   | `GNEWS_API_KEY` | The gnews.io key (for the news ticker). |
   | `SIDELINE_ACCESS_CODE` | Any code you make up, for example three words. Give it only to the people you want making segments. |

5. **Wait for it to build.** The Space restarts after the secrets are added. The first build takes about 5 minutes; the status at the top changes from **Building** to **Running**.
6. **Open it** at `https://<your-username>-sideline.hf.space`.

## Good to know

- **Free Spaces sleep** after 48 hours with no visitors. Opening the link wakes it up, which takes a minute or two.
- **The first segment after a restart is slower** (about 3 minutes instead of 2) while it downloads the sports data.
- **New code from GitHub:** the Space picks it up the next time it builds. To force that, choose **Factory rebuild** from the menu next to the Space's status.
- **Segments made online stay online.** They're saved inside the Space (the newest 10) and are lost when it restarts. The 10 saved segments in this repo always come back.
- **Turning it off after grading:** **Settings → Pause Space**, and delete the API key you made for it in the Anthropic console.
