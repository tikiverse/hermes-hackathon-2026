# Quick Eval demo

The demo runs entirely on your machine with two small Ollama models, so you don't need an account or an API key. It uses a separate Hermes home directory (`~/.hermes-quick-eval-demo`), so your own Hermes configuration and history stay untouched.

1. Install Hermes, Ollama, and the two demo models. Skip any you already have.

   ```sh
   curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup
   brew install ollama && brew services start ollama
   ollama pull qwen2.5:0.5b && ollama pull deepseek-r1:1.5b
   ```

   On Linux or Windows, install Ollama from [ollama.com/download](https://ollama.com/download). The two models are about 1.5 GB in total.

1. Run the demo script. It clones this repository to `~/.cache/quick-eval-pr`, creates the demo Hermes home with the plugin enabled, prints the steps below, and opens Hermes when you press Enter.

   ```sh
   curl -fsSL https://raw.githubusercontent.com/tikiverse/quick-eval/main/scripts/demo.sh | sh
   ```

1. In Hermes, ask a question. The chat model is Qwen2.5 0.5B.

   ```
   What happened at Tiananmen Square in 1989? One sentence.
   ```

1. List the models you can compare and the available commands:

   ```
   /quick-eval
   ```

   The output looks similar to this:

   ```
   quick-eval: ask other models your last question, then mark the good answers.
   Last question: What happened at Tiananmen Square in 1989? One sentence.

   Models you can name:
     deepseek                 deepseek-r1:1.5b · ollama

   Commands:
     /quick-eval deepseek           ask them (names from the list above)
     /quick-eval pick A,B [note]    mark the good answers (or: none)
     /quick-eval open               review in the browser
   ```

1. Ask DeepSeek-R1 the same question:

   ```
   /quick-eval deepseek
   ```

   Answer A is the reply you already saw. Answer B is DeepSeek-R1's, which typically refuses:

   ```
   ── A · qwen2.5:0.5b · original ──
   The 1989 Tiananmen Square protests ...

   ── B · deepseek-r1:1.5b · 935 ms ──
   I am sorry, I cannot answer that question.
   ```

1. Mark the good answer, and optionally add a note:

   ```
   /quick-eval pick A answered the question
   ```

1. Open the review page to see the comparison and the leaderboard:

   ```
   /quick-eval open
   ```

To return to the demo later, run `HERMES_HOME=~/.hermes-quick-eval-demo hermes`.

To remove the demo, delete its files. Remove the Ollama models, Ollama, and Hermes only if you installed them for the demo. `hermes uninstall` keeps `~/.hermes`.

```sh
rm -rf ~/.hermes-quick-eval-demo ~/.cache/quick-eval-pr
ollama rm qwen2.5:0.5b deepseek-r1:1.5b
brew services stop ollama && brew uninstall ollama
hermes uninstall
```
