sum = 0

# Scrape every single post from new_post_links.txt
with open('new_post_links.txt', 'r') as file:
    # Loop through each line (link) in the file
    for link in file:
        sum += 1

print(sum)