# Morpho-steak-cli

Welcome to the morpho-steak-cli python project! This README will guide you through setting up your development environment to ensure you're working with the correct version of Python and isolated environments for dependencies. We'll be using Python 3.11 and a virtual environment for this setup.

## Prerequisites

- **Python 3.11**: Ensure Python 3.11 is installed on your system. If not, download and install it from the [official Python website](https://www.python.org/downloads/).

## Step 1: Fork and Clone the Project Repository from Github

### Fork the Repository:

- Visit the GitHub page for the project: https://github.com/Steakhouse-Financial/morpho-steak-cli
- Click the Fork button on the upper right-hand side of the page to create your own copy of the repository.

### Clone Your Forked Repository:

Once the repository is forked, you will be redirected to your copy of the repository on GitHub.
Clone your forked repository to your local machine by using the following command in your terminal or command prompt, replacing YOUR_USERNAME with your GitHub username:

`git clone https://github.com/YOUR_USERNAME/morpho-steak-cli.git`

Navigate into the project directory:

`cd morpho-steak-cli`

## Step 2: Creating the Virtual Environment

The virtual environment isn't nesssary, but highly recomended to separate this project from your system's dependencies

- Navigate to the main project directory in your terminal
- Create the virtual environment named `venv` using Python 3.11:
  `python3.11 -m venv venv`

This command creates a new directory named `venv` in your project folder, which contains the Python executable and a copy of the pip library.

## Step 3: Activating the Virtual Environment

Before installing the project's dependencies, you must activate the virtual environment. The activation command differs depending on your operating system:

- **Windows:**
  `.\venv\Scripts\activate`
- **macOS and Linux:**
  `source venv/bin/activate`

You'll know the virtual environment is activated when you see `(venv)` preceding your command prompt like below.

`(venv) user:~/morpho-steak-cli$ `

## Step 4: Installing Dependencies

With the virtual environment activated, install the project's dependencies using pip and the `requirements.txt` file:

- `pip install -r requirements.txt`

This command installs all the dependencies listed in the `requirements.txt` file into the virtual environment.

## Step 5: Setting Up the .env File

To configure your project environment:

1. **Copy the `.env-default` file to a new file named `.env`** in the root of your project directory:
   `cp .env-default .env`
2. **Edit the `.env` file** to include your specific configurations. Specifically, you will need to replace the `WEB3_HTTP_PROVIDER` placeholder with your Infura API URL.
3. This is in the .gitignore file so **don't change the name from .env**

## Step 6: Verifying the Installation

After installing the dependencies and setting up your .env file, you can verify that everything is set up correctly by running:
`python morpho-cli.py summary.`

It should output something like:

`steakUSDC - Steakhouse USDC - Assets: 27,612,869.62 - 13:04:28`
`USDC[sDAI] - rates: 1.50%/1.67%[1.66%] exposure: 0 (0.0%), util: 90.0%, vault %: 0.0%`
`USDC[WBTC] - rates: 9.35%/10.35%[9.28%] exposure: 3,360,472 (12.2%), util: 90.4%, vault %: 74.9%`
`USDC[wstETH] - rates: 9.72%/10.82%[10.83%] exposure: 24,252,397 (87.8%), util: 89.8%, vault %: 75.1%`
`USDC[wbIB01] - rates: 0.00%/1.64%[6.56%] exposure: 0 (0.0%), util: 0.0%, vault %: 0.0%`
`USDC[Idle] - exposure: 0 (0.0%), vault %: 0.0%
steakUSDC rate 9.67%, total liquidity 3,715,934`

## Ruff - Code Formatting and Linting

We use Ruff, a fast Python linter and formatter, to ensure our codebase remains clean and adheres to our project standards. Ruff helps catch errors and enforces a consistent coding style. It is in the requirements.txt file as a dependency.

- **Ruff Documentation**: For detailed usage and configuration options, visit [Ruff's documentation](https://docs.astral.sh/ruff/).

### Setting Up Ruff

1. **Manual Linting and Formatting**:
   - To manually check your code for issues, run: `ruff check`.
   - To format your code run: `ruff format`.
2. **Ruff Pre-commit Hook**: To enforce our formatting we run a [Ruff pre-commit hook](https://github.com/astral-sh/ruff-pre-commit).
   - This will run with git commit automatically, enforcing formatting standards.
   - If there is an error, it will show failed and attempt to fix the error.
   - If the error is fixed by the hook, just rerun the commit command
   - Run ruff check in the terminal to get better details on errors

### Integration with VS Code

If using VS Code there are a few ways to augment Ruff:

- **VS Code Extension**: Install the Ruff extension for VS Code by searching for `charliermarsh.ruff` in the Extensions view (`Ctrl+Shift+X`).

- **Auto-format on Save**:
  To configure VS Code to automatically format your Python files with Ruff upon saving, add the following settings to your `settings.json` file:

      ```
      {
        "[python]": {
          "editor.formatOnSave": true,
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
      ```

## Token and Morpho Caching

Token and Morpho details are cached when first run to prevent excess API calls to get their information, which typically remains constant. The details are saved in the `data` directory, with cache files named `morpho_cache.json` and `token_cache.json`. If you need to refresh the cached data and start fresh, follow the steps below to clear the contents of these files.

### Clearing Cache on macOS and Linux

Open your terminal, navigate to the project root, and run the following commands to clear the cache:

```sh
echo "" > data/morpho_cache.json
echo "" > data/token_cache.json
```

### Clearing Cache on Windows

Open Command Prompt or PowerShell, navigate to the project root, and use these commands to clear the cache:

```cmd
echo. > data\morpho_cache.json
echo. > data\token_cache.json
```

Note: The echo. command in Windows creates a new line in the file. Since the goal is to empty the file, this achieves the effect of "clearing" the content, as the new content will just be a newline character.

### Starting the CLI Fresh

After clearing the cache, you can run the CLI again to regenerate the cache files with fresh data:

```
python morpho-cli.py
```

This command starts the CLI, and if it does not find existing cache files, it will fetch the details again and recreate the cache files in the data directory.
