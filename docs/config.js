/* Public settings for the page. Nothing secret goes here: these values are visible to every visitor.
   api          address of your catalog API (Render), no trailing slash. Empty = the search box says the catalog isn't connected.
   supabaseUrl  your Supabase project URL, and supabaseKey its "anon public" key (safe to publish), for Google sign-in. */
window.CF = Object.assign({ api: "https://chordflow-api.onrender.com", supabaseUrl: "", supabaseKey: "" }, window.CF || {});
