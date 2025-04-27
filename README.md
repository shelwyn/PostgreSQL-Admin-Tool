# PostgreSQL Admin Tool

A comprehensive web-based PostgreSQL database administration tool built with Streamlit. This application provides a user-friendly interface for database administrators and developers to interact with PostgreSQL databases without writing SQL code directly.


## Features

- **Database Connection Management**: Connect to any PostgreSQL database with authentication
- **Database Explorer**: Browse schemas and tables with an intuitive interface
- **Data Viewer**: View table data with filtering and sorting options
- **Schema Browser**: Explore table structures, primary keys, foreign keys, and indexes
- **SQL Editor**: Execute custom SQL queries with a query history feature
- **Table Management**: Create, modify, and drop tables through a GUI interface

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- Access to a PostgreSQL database

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/shelwyn/PostgreSQL-Admin-Tool.git
   cd postgresql-admin-tool
   ```

2. Create a virtual environment (recommended):
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python -m streamlit run app.py
   ```

2. The application will start and open in your default web browser at `http://localhost:8501`

3. Connect to your PostgreSQL database using the connection form in the sidebar

### Connection Parameters

- **Host**: The host address of your PostgreSQL server (e.g., localhost)
- **Port**: The port number (default is 5432)
- **Database**: The name of the database you want to connect to
- **User**: PostgreSQL username
- **Password**: PostgreSQL password

## Development

### Project Structure

```
postgresql-admin-tool/
├── app.py          # Main application file
├── requirements.txt # Python dependencies
├── README.md       # This file
└── screenshot.png  # Application screenshot (optional)
```

### Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some feature'`)
5. Push to the branch (`git push origin feature/your-feature`)
6. Open a Pull Request

## Security Considerations

This tool provides direct access to your database, so please be careful with the following:

- Don't expose this tool on public networks without proper security measures
- Be cautious when executing SQL queries, especially DELETE or DROP operations
- Consider using a read-only database user for safer browsing
- Never commit database credentials to version control

## License

[MIT License](LICENSE)

## Acknowledgements

- [Streamlit](https://streamlit.io/)
- [psycopg2](https://www.psycopg.org/)
- [pandas](https://pandas.pydata.org/)
