# Pet Parent Games

Streamlit game with animal matching, timed trivia, host controls, GIF results,
ranked leaderboards, and confetti.

Deploy `app.py` on Streamlit Community Cloud using Python 3.12.
Set `PET_GAME_PUBLIC_URL` to the deployed https://...streamlit.app address in
Streamlit Advanced settings → Secrets, so the join QR code uses the fixed link.
Set `PET_GAME_HOST_PIN` in the same Secrets panel to configure host access.
Do not add secrets.toml or a game database to this repository.

The cloud app starts with a fresh game. SQLite scores are live-server data and
may reset if the hosting environment reboots or redeploys. The public address
stays the same. Open and test the app before the presentation.
