import sys
from playwright.sync_api import sync_playwright
import time
import pandas as pd
from rich import print
from bs4 import BeautifulSoup

def xx():
    print("Hi")

def scroll_down():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # Use headless to reduce resource usage
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 1080})
            page.goto("https://www.espncricinfo.com/records/tournament/team-match-results/icc-men-s-t20-world-cup-2022-23-14450")

            page.wait_for_load_state('domcontentloaded')  # Ensure the page loads before interacting with it

            # Try to click the cookie accept button, if it exists
            try:
                page.click("#hf_cookie_text_cookieAccept", timeout=5000)
            except Exception as e:
                print("Cookie accept button not found or could not be clicked:", e)

            # Wait for a specific element instead of "networkidle"
            try:
                page.wait_for_selector("footer", timeout=60000)  # Wait for the footer to load
            except Exception as e:
                print("Timeout while waiting for the page to load:", e)

            # Scroll down
            for x in range(1, 5):
                page.keyboard.press("End")
                print("scrolling key press", x)
                time.sleep(1)

            # Get the HTML content of the page
            html_content = page.content()

            # Save the HTML content to a file
            with open("page_content.html", "w", encoding="utf-8") as file:
                file.write(html_content)

            # Close the browser and context
            context.close()
            browser.close()
    except Exception as e:
        print(f"An error occurred: {e}")

def extract():
    with open("page_content.html", "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    thead = soup.find('thead', class_='ds-bg-fill-content-alternate ds-text-left')
    tbody = soup.find('tbody')

    # Extract headers
    if thead:
        headers = [header.get_text(strip=True) for header in thead.find_all('span', class_='ds-cursor-pointer')]
        headers.append("Scorecard Link")  # Include the scorecard link in the headers
        print("Headers found:", headers)
    else:
        print("Thead not found")
        headers = []

    # Extract rows
    if tbody:
        rows = []
        for tr in tbody.find_all('tr'):
            row = [td.get_text(strip=True) for td in tr.find_all('td')]
            scorecard_link = tr.find_all('a', href=True)[-1]  # Only get the last 'a' tag which should be the Scorecard link
            if scorecard_link:
                row.append(scorecard_link['href'])
            else:
                row.append(None)
            rows.append(row)
        print("Rows found:", rows)
    else:
        print("Tbody not found")
        rows = []

    return headers, rows

def save_to_excel(headers, rows, filename):
    # Create a DataFrame
    df = pd.DataFrame(rows, columns=headers)

    # Save to Excel file
    df.to_excel(filename, index=False)
    print(f"Data saved to {filename}")

def extract_scorecard_data(link, match_id):
    if not link:
        return [], []

    base_url = "https://www.espncricinfo.com"
    scorecard_url = f"{base_url}{link}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # Use headless to reduce resource usage
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 1080})
            page.goto(scorecard_url)

            # Wait for page to load
            page.wait_for_load_state('domcontentloaded')

            html_content = page.content()

            # Close the browser and context
            context.close()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all team innings divs and tables
        innings_divs = soup.find_all('div', class_='ds-flex ds-px-4 ds-border-b ds-border-line ds-py-3 ds-bg-ui-fill-translucent-hover')
        tables = soup.find_all('table', class_='ds-w-full ds-table ds-table-md ds-table-auto ci-scorecard-table')

        if not innings_divs or not tables or len(innings_divs) != len(tables):
            print(f"Mismatch in number of innings divs and tables at {scorecard_url}")
            return [], []

        # Extract match details
        match_details = soup.find('h1', class_='ds-text-title-xs ds-font-bold ds-mb-2 ds-m-1')
        if match_details:
            match_text = match_details.get_text(strip=True)
            match = match_text.split(",")[0]
        else:
            match = "Unknown Match"

        headers = [
            'match', 'teamInnings', 'battingPos', 'batsmanName',
            'runs', 'balls', '4s', '6s', 'SR', 'out/not_out', 'match_id'
        ]
        rows = []

        for innings_div, table in zip(innings_divs, tables):
            team_innings = innings_div.get_text(strip=True).split('(')[0].strip()
            batting_pos = 1  # Reset batting position for each team innings

            for tr in table.find_all('tr'):
                if tr.find_all('td'):
                    tds = tr.find_all('td')
                    if len(tds) < 8:  # Skip rows that do not have the expected number of columns
                        continue

                    batsman_name = tds[0].get_text(strip=True)
                    if batsman_name in ['Did not bat', 'Extras', 'Total', 'Did not bat -']:
                        continue

                    runs = tds[2].get_text(strip=True)
                    balls = tds[3].get_text(strip=True)
                    fours = tds[5].get_text(strip=True)
                    sixes = tds[6].get_text(strip=True)
                    sr = tds[7].get_text(strip=True)

                    # Determine out/not_out status by checking the text content in the nested span
                    dismissal_td = tds[1].find('span')
                    out_not_out = ""
                    if dismissal_td:
                        dismissal_info = dismissal_td.find_all('span')
                        if len(dismissal_info) > 1:
                            out_not_out = dismissal_info[1].get_text(strip=True)
                        else:
                            out_not_out = dismissal_td.get_text(strip=True)

                    if out_not_out == "":
                        out_not_out = "not out"
                    else:
                        out_not_out = "out"

                    row = [
                        match, team_innings, batting_pos, batsman_name,
                        runs, balls, fours, sixes, sr, out_not_out, match_id
                    ]
                    rows.append(row)
                    batting_pos += 1

        return headers, rows

    except Exception as e:
        print(f"An error occurred while extracting scorecard data from {scorecard_url}: {e}")
        return [], []


def extract_bowling(link, match_id):
    if not link:
        return [], []

    base_url = "https://www.espncricinfo.com"
    scorecard_url = f"{base_url}{link}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # Use headless to reduce resource usage
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 1080})
            page.goto(scorecard_url)

            # Wait for page to load
            page.wait_for_load_state('domcontentloaded')

            html_content = page.content()

            # Close the browser and context
            context.close()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all team innings divs and bowling tables
        innings_divs = soup.find_all('div', class_='ds-flex ds-px-4 ds-border-b ds-border-line ds-py-3 ds-bg-ui-fill-translucent-hover')
        bowling_tables = soup.find_all('table', class_='ds-w-full ds-table ds-table-md ds-table-auto')

        if not innings_divs or not bowling_tables or len(innings_divs) != len(bowling_tables):
            print(f"Mismatch in number of innings divs and tables at {scorecard_url}")
            return [], []

        # Extract match details
        match_details = soup.find('h1', class_='ds-text-title-xs ds-font-bold ds-mb-2 ds-m-1')
        if match_details:
            match_text = match_details.get_text(strip=True)
            match = match_text.split(",")[0]
        else:
            match = "Unknown Match"

        headers = [
            'match', 'bowlingTeam', 'bowlerName', 'overs', 'maiden', 'runs', 'wickets',
            'economy', '0s', '4s', '6s', 'wides', 'noBalls', 'match_id'
        ]
        rows = []

        for innings_div, table in zip(innings_divs, bowling_tables):
            bowling_team = innings_div.get_text(strip=True).split('(')[0].strip()
            for tr in table.find('tbody').find_all('tr'):
                if tr.find_all('td'):
                    tds = tr.find_all('td')
                    if len(tds) < 11:  # Ensure the row has the correct number of columns
                        continue

                    bowler_name = tds[0].get_text(strip=True)
                    overs = tds[1].get_text(strip=True)
                    maiden = tds[2].get_text(strip=True)
                    runs = tds[3].get_text(strip=True)
                    wickets = tds[4].get_text(strip=True)
                    economy = tds[5].get_text(strip=True)
                    zeros = tds[6].get_text(strip=True)
                    fours = tds[7].get_text(strip=True)
                    sixes = tds[8].get_text(strip=True)
                    wides = tds[9].get_text(strip=True)
                    no_balls = tds[10].get_text(strip=True)

                    row = [
                        match, bowling_team, bowler_name, overs, maiden, runs, wickets,
                        economy, zeros, fours, sixes, wides, no_balls, match_id
                    ]
                    rows.append(row)

        return headers, rows

    except Exception as e:
        print(f"An error occurred while extracting bowling data from {scorecard_url}: {e}")
        return [], []

def extract_player_details(player_link, team):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 1080})
            page.goto(player_link)

            # Wait for page to load
            page.wait_for_load_state('domcontentloaded')

            player_html_content = page.content()

            # Close the browser and context
            context.close()
            browser.close()

        player_soup = BeautifulSoup(player_html_content, 'html.parser')

        # Extract player details
        name_elem = player_soup.find('div', class_='ds-text-title-s ds-font-bold ds-text-typo')
        name = name_elem.text.strip() if name_elem else 'N/A'

        image_elem = player_soup.find('img', class_='ds-rounded-full')
        image = image_elem['src'] if image_elem else ''

        batting_style_elem = player_soup.find(string='Batting Style')
        batting_style = batting_style_elem.find_next('p').text.strip() if batting_style_elem else 'N/A'

        bowling_style_elem = player_soup.find(string='Bowling Style')
        bowling_style = bowling_style_elem.find_next('p').text.strip() if bowling_style_elem else 'N/A'

        playing_role_elem = player_soup.find(string='Playing Role')
        playing_role = playing_role_elem.find_next('p').text.strip() if playing_role_elem else 'N/A'

        description_elem = player_soup.find('p', class_='ci-player-bio')
        description = description_elem.text.strip() if description_elem else 'N/A'

        return {
            'name': name,
            'team': team,
            'image': image,
            'battingStyle': batting_style,
            'bowlingStyle': bowling_style,
            'playingRole': playing_role,
            'description': description
        }
    except Exception as e:
        print(f"An error occurred while extracting details for {player_link}: {e}")
        return {}

def extract_players(link, existing_links):
    players_data = []
    base_url = "https://www.espncricinfo.com"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 1080})
            page.goto(link)

            # Wait for page to load
            page.wait_for_load_state('domcontentloaded')

            html_content = page.content()

            # Close the browser and context
            context.close()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Find team names
        match_divs = soup.find_all('div', class_='ds-flex ds-px-4 ds-border-b ds-border-line ds-py-3 ds-bg-ui-fill-translucent-hover')
        if len(match_divs) < 2:
            return []

        team1 = match_divs[0].get_text(strip=True).replace(" Innings", "")
        team2 = match_divs[1].get_text(strip=True).replace(" Innings", "")

        # For batting players
        tables = soup.find_all('table', class_='ci-scorecard-table')
        if len(tables) < 2:
            return []

        first_inning_rows = tables[0].find('tbody').find_all('tr')
        second_inning_rows = tables[1].find('tbody').find_all('tr')

        for row in first_inning_rows:
            tds = row.find_all('td')
            if len(tds) >= 8:
                player_name = tds[0].get_text(strip=True).replace(' ', '')
                player_link = base_url + tds[0].find('a')['href']
                if player_link not in existing_links:
                    player_details = extract_player_details(player_link, team1)
                    if player_details:
                        players_data.append(player_details)
                        existing_links.add(player_link)

        for row in second_inning_rows:
            tds = row.find_all('td')
            if len(tds) >= 8:
                player_name = tds[0].get_text(strip=True).replace(' ', '')
                player_link = base_url + tds[0].find('a')['href']
                if player_link not in existing_links:
                    player_details = extract_player_details(player_link, team2)
                    if player_details:
                        players_data.append(player_details)
                        existing_links.add(player_link)

        # For bowling players
        bowling_tables = soup.find_all('table', class_='ds-table')
        if len(bowling_tables) < 4:
            return []

        first_bowling_rows = bowling_tables[1].find('tbody').find_all('tr')
        second_bowling_rows = bowling_tables[3].find('tbody').find_all('tr')

        for row in first_bowling_rows:
            tds = row.find_all('td')
            if len(tds) >= 11:
                player_name = tds[0].get_text(strip=True).replace(' ', '')
                player_link = base_url + tds[0].find('a')['href']
                if player_link not in existing_links:
                    player_details = extract_player_details(player_link, team2)
                    if player_details:
                        players_data.append(player_details)
                        existing_links.add(player_link)

        for row in second_bowling_rows:
            tds = row.find_all('td')
            if len(tds) >= 11:
                player_name = tds[0].get_text(strip=True).replace(' ', '')
                player_link = base_url + tds[0].find('a')['href']
                if player_link not in existing_links:
                    player_details = extract_player_details(player_link, team1)
                    if player_details:
                        players_data.append(player_details)
                        existing_links.add(player_link)

        return players_data

    except Exception as e:
        print(f"An error occurred while extracting player data from {link}: {e}")
        return []





if __name__ == '__main__':
    xx()
    scroll_down()
    headers, rows = extract()
    save_to_excel(headers, rows, "t20_worldcup_match_results.xlsx")
    all_data = []
    final_headers = []
    #
    # for row in rows:
    #     scorecard_link = row[-1]
    #     match_id = row[-2]  # Assuming match_id is in the second last column of rows
    #     headers, scorecard_rows = extract_scorecard_data(scorecard_link, match_id)
    #     if scorecard_rows:
    #         final_headers = headers  # Update headers with the correct ones
    #         all_data.extend(scorecard_rows)
    #
    # if all_data:  # Save only if there is data
    #     save_to_excel(final_headers, all_data, "t20_worldcup_scorecards.xlsx")
    # else:
    #     print("No scorecard data found to save.")

    # for row in rows:
    #     scorecard_link = row[-1]
    #     match_id = row[-2]  # Assuming match_id is in the first column of rows
    #     headers, bowling_rows = extract_bowling(scorecard_link, match_id)
    #     if bowling_rows:
    #         final_headers = headers  # Update headers with the correct ones
    #         all_data.extend(bowling_rows)
    #
    # if all_data:  # Save only if there is data
    #     save_to_excel(final_headers, all_data, "t20_worldcup_bowling_figures.xlsx")
    # else:
    #     print("No bowling data found to save.")

    all_players = []
    existing_links = set()

    for row in rows:
        scorecard_link = row[-1]
        players = extract_players(f"https://www.espncricinfo.com{scorecard_link}", existing_links)
        all_players.extend(players)

    if all_players:
        player_headers = ["name", "team", "image", "battingStyle", "bowlingStyle", "playingRole", "description"]
        player_rows = [[player["name"], player["team"], player["image"], player["battingStyle"], player["bowlingStyle"], player["playingRole"], player["description"]] for player in all_players]
        save_to_excel(player_headers, player_rows, "t20_worldcup_players.xlsx")
    else:
        print("No player data found to save.")
