from flask import Flask, render_template, request, redirect, url_for, session
import requests
from collections import Counter

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a real secret key

# Replace with your actual TMDb API key and Utelly API key
TMDB_API_KEY = '86a3b75810ef5efee8ce07ece18836d8'
UTELLY_API_KEY = '15e4e892damshb4de28b338b1720p190b2ajsn8c39e5893290'

# Function to fetch movie streaming availability from Utelly API
def get_streaming_data(movie_title):
    url = "https://utelly-tv-shows-and-movies-availability-v1.p.rapidapi.com/lookup"
    querystring = {"term": movie_title}
    headers = {
        "X-RapidAPI-Key": UTELLY_API_KEY,
        "X-RapidAPI-Host": "utelly-tv-shows-and-movies-availability-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    
    # Debugging: Print the API response for each movie
    print(f"Fetching platforms for {movie_title}...")
    print(f"API Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        platforms = []
        if 'results' in data and data['results']:
            for location in data['results'][0]['locations']:
                platforms.append(location['display_name'])
        return platforms
    else:
        return []


# Home page to specify the number of family members
@app.route('/')
def home():
    return render_template('index.html')

# Handle form submission to set the number of family members
@app.route('/set_members', methods=['POST'])
def set_members():
    # Get the number of family members from the form
    num_members = int(request.form['num_members'])
    
    # Store the number of family members in the session
    session['num_members'] = num_members
    
    # Redirect to the next page where each family member can enter their preferences
    return redirect(url_for('member_preferences'))

# Dynamically generate the form for each family member to input preferences
@app.route('/member_preferences')
def member_preferences():
    # Get the number of family members from the session
    num_members = session.get('num_members', 1)  # Default to 1 if not set
    return render_template('member_preferences.html', num_members=num_members)

# Process the movie preferences and recommend movies
@app.route('/recommend', methods=['POST'])
def recommend():
    # Get the number of family members from the session
    num_members = session.get('num_members', 1)
    all_genres = []
    min_ratings = []
    languages = []
    
    # Gather preferences for each family member
    for i in range(1, num_members + 1):
        genres = request.form.getlist(f'member_{i}_genres')
        min_rating = request.form.get(f'member_{i}_min_rating')
        language = request.form.get(f'member_{i}_language')
        
        # Ensure valid float input for rating
        if min_rating:
            min_ratings.append(float(min_rating))
        all_genres.extend(genres)
        
        # Collect language preferences
        if language:
            languages.append(language)
    
    # Find the most common genres across the family
    if not all_genres:
        return "No genres selected. Please select at least one genre."
    
    genre_counter = Counter(all_genres)
    common_genres = [genre for genre, count in genre_counter.most_common(3)]  # Top 3 genres
    
    # Calculate average minimum rating
    avg_min_rating = sum(min_ratings) / len(min_ratings) if min_ratings else 0  # Default to 0 if no ratings provided
    
    # Determine the most common language (or use a default like "en")
    language_counter = Counter(languages)
    most_common_language = language_counter.most_common(1)[0][0] if languages else 'en'
    
    # Get year range
    min_year = request.form.get('min_year', '2000')
    max_year = request.form.get('max_year', '2023')
    
    # Construct API request to TMDb
    url = f"https://api.themoviedb.org/3/discover/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'sort_by': 'popularity.desc',
        'include_adult': 'false',
        'with_genres': ','.join(common_genres),
        'primary_release_date.gte': f"{min_year}-01-01",
        'primary_release_date.lte': f"{max_year}-12-31",
        'vote_average.gte': avg_min_rating,
        'with_original_language': most_common_language,  # Use the most common language
        'page': 1  # Fetch the first page of results
    }

    # Make the API request and handle errors
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        movies = response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        return f"Error fetching movie data: {str(e)}"

    if not movies:
        return "No movies found. Please try different search criteria."

    # Get movie IDs from the top 10 movies
    movie_ids = [movie['id'] for movie in sorted(movies, key=lambda x: x['vote_average'], reverse=True)[:10]]
    
    # Save the movie IDs to the session
    session['movie_ids'] = movie_ids
    return redirect(url_for('results'))

# Display the recommended movies and fetch streaming data
@app.route('/results')
def results():
    movie_ids = session.get('movie_ids', [])
    
    # If no movie IDs were stored, return to the home page
    if not movie_ids:
        return "No movies found. Please try again."
    
    movies = []
    for movie_id in movie_ids:
        # Fetch full movie details for each ID
        movie_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'en-US'
        }
        try:
            response = requests.get(movie_url, params=params)
            response.raise_for_status()
            movie = response.json()

            # Fetch streaming platforms for the movie
            platforms = get_streaming_data(movie['title'])
            movie['platforms'] = platforms  # Add platforms to the movie data

            movies.append(movie)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching details for movie ID {movie_id}: {str(e)}")
    
    return render_template('results.html', movies=movies)

if __name__ == '__main__':
    app.run(debug=True)
