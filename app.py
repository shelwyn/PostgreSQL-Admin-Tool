import streamlit as st
import psycopg2
import pandas as pd
from psycopg2 import sql
import re

st.set_page_config(
    page_title="PostgreSQL Admin Tool",
    page_icon="🐘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem;}
    .stButton button {width: 100%;}
    .sql-query {
        background-color: #f0f0f0;
        border-radius: 5px;
        padding: 10px;
        font-family: monospace;
    }
    h1, h2, h3 {margin-bottom: 0.5rem;}
    .stAlert {margin-top: 1rem;}
    .table-container {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables if they don't exist
if 'connection' not in st.session_state:
    st.session_state.connection = None
if 'cursor' not in st.session_state:
    st.session_state.cursor = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'schemas' not in st.session_state:
    st.session_state.schemas = []
if 'selected_schema' not in st.session_state:
    st.session_state.selected_schema = None
if 'tables' not in st.session_state:
    st.session_state.tables = []
if 'selected_table' not in st.session_state:
    st.session_state.selected_table = None
if 'query_history' not in st.session_state:
    st.session_state.query_history = []

# Function to connect to the database
def connect_to_db(host, port, database, user, password):
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        st.session_state.connection = conn
        st.session_state.cursor = cursor
        st.session_state.connected = True
        st.success("Connected to PostgreSQL database!")
        return True
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return False

# Function to disconnect from the database
def disconnect_db():
    if st.session_state.cursor:
        st.session_state.cursor.close()
    if st.session_state.connection:
        st.session_state.connection.close()
    st.session_state.connected = False
    st.session_state.connection = None
    st.session_state.cursor = None
    st.session_state.schemas = []
    st.session_state.selected_schema = None
    st.session_state.tables = []
    st.session_state.selected_table = None
    st.success("Disconnected from database.")

# Function to get all schemas
def get_schemas():
    try:
        st.session_state.cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schema_name;
        """)
        schemas = [row[0] for row in st.session_state.cursor.fetchall()]
        st.session_state.schemas = schemas
        return schemas
    except Exception as e:
        st.error(f"Error fetching schemas: {e}")
        return []

# Function to get all tables in a schema
def get_tables(schema):
    try:
        st.session_state.cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY table_name;
        """, (schema,))
        tables = [row[0] for row in st.session_state.cursor.fetchall()]
        st.session_state.tables = tables
        return tables
    except Exception as e:
        st.error(f"Error fetching tables: {e}")
        return []

# Function to get table structure
def get_table_structure(schema, table):
    try:
        # Get columns info
        st.session_state.cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
        """, (schema, table))
        columns = st.session_state.cursor.fetchall()
        
        # Get primary key info
        st.session_state.cursor.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            ORDER BY kcu.ordinal_position;
        """, (schema, table))
        primary_keys = [row[0] for row in st.session_state.cursor.fetchall()]
        
        # Get foreign key info
        st.session_state.cursor.execute("""
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            ORDER BY kcu.ordinal_position;
        """, (schema, table))
        foreign_keys = st.session_state.cursor.fetchall()
        
        # Get indexes
        st.session_state.cursor.execute("""
            SELECT
                i.relname AS index_name,
                a.attname AS column_name,
                ix.indisunique AS is_unique
            FROM
                pg_class t,
                pg_class i,
                pg_index ix,
                pg_attribute a,
                pg_namespace n
            WHERE
                t.oid = ix.indrelid
                AND i.oid = ix.indexrelid
                AND a.attrelid = t.oid
                AND a.attnum = ANY(ix.indkey)
                AND t.relkind = 'r'
                AND t.relnamespace = n.oid
                AND n.nspname = %s
                AND t.relname = %s
            ORDER BY
                i.relname, a.attnum;
        """, (schema, table))
        indexes = st.session_state.cursor.fetchall()
        
        return {
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes
        }
    except Exception as e:
        st.error(f"Error fetching table structure: {e}")
        return None

# Function to get table data
def get_table_data(schema, table, limit=100, offset=0, where_clause=None, order_by=None):
    try:
        # Create the query
        query = sql.SQL("SELECT * FROM {}.{}").format(
            sql.Identifier(schema),
            sql.Identifier(table)
        )
        
        # Add WHERE clause if provided
        params = []
        if where_clause:
            query = sql.SQL("{} WHERE {}").format(query, sql.SQL(where_clause))
        
        # Add ORDER BY if provided
        if order_by:
            query = sql.SQL("{} ORDER BY {}").format(query, sql.SQL(order_by))
        
        # Add LIMIT and OFFSET
        query = sql.SQL("{} LIMIT {} OFFSET {}").format(query, sql.Literal(limit), sql.Literal(offset))
        
        # Execute the query
        st.session_state.cursor.execute(query)
        data = st.session_state.cursor.fetchall()
        
        # Get column names
        col_names = [desc[0] for desc in st.session_state.cursor.description]
        
        return pd.DataFrame(data, columns=col_names)
    except Exception as e:
        st.error(f"Error fetching table data: {e}")
        return None

# Function to execute SQL query
def execute_query(query):
    try:
        st.session_state.cursor.execute(query)
        st.session_state.connection.commit()
        
        # Add query to history
        if query.strip() not in st.session_state.query_history:
            st.session_state.query_history.append(query.strip())
            if len(st.session_state.query_history) > 10:
                st.session_state.query_history.pop(0)
        
        # Check if the query returns data
        if st.session_state.cursor.description:
            data = st.session_state.cursor.fetchall()
            col_names = [desc[0] for desc in st.session_state.cursor.description]
            result_df = pd.DataFrame(data, columns=col_names)
            return {
                "success": True,
                "message": f"Query executed successfully. Rows returned: {len(data)}",
                "data": result_df
            }
        else:
            return {
                "success": True,
                "message": f"Query executed successfully. Rows affected: {st.session_state.cursor.rowcount}",
                "data": None
            }
    except Exception as e:
        st.session_state.connection.rollback()
        return {
            "success": False,
            "message": f"Error executing query: {e}",
            "data": None
        }

# Function to create a new table
def create_table(schema, table_name, columns):
    try:
        # Build the CREATE TABLE query
        query = f"CREATE TABLE {schema}.{table_name} (\n"
        query += ",\n".join(columns)
        query += "\n);"
        
        # Execute the query
        result = execute_query(query)
        return result
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating table: {e}",
            "data": None
        }

# Main application header
st.title("🐘 PostgreSQL Admin Tool")

# Sidebar for connection and navigation
with st.sidebar:
    st.header("Database Connection")
    
    if not st.session_state.connected:
        with st.form("connection_form"):
            host = st.text_input("Host", "<HOST>")
            port = st.text_input("Port", "<PORT>")
            database = st.text_input("Database", "<DATABASE>")
            user = st.text_input("User", "<USER>")
            password = st.text_input("Password", "<PASSWORD>", type="password")
            
            submit_button = st.form_submit_button("Connect")
            
            if submit_button:
                connect_to_db(host, port, database, user, password)
                if st.session_state.connected:
                    get_schemas()
    else:
        st.success("Connected to database")
        if st.button("Disconnect"):
            disconnect_db()
    
    if st.session_state.connected:
        st.header("Navigation")
        
        # Schema selection
        schema_option = st.selectbox(
            "Select Schema",
            options=st.session_state.schemas,
            key="schema_selector",
            on_change=lambda: setattr(st.session_state, 'selected_schema', st.session_state.schema_selector)
        )
        
        if schema_option:
            st.session_state.selected_schema = schema_option
            tables = get_tables(schema_option)
            
            # Table selection
            table_option = st.selectbox(
                "Select Table",
                options=tables,
                key="table_selector",
                on_change=lambda: setattr(st.session_state, 'selected_table', st.session_state.table_selector)
            )
            
            if table_option:
                st.session_state.selected_table = table_option

# Main content area
if st.session_state.connected:
    # Create tabs for different functionalities
    tabs = st.tabs(["Database Explorer", "SQL Editor", "Table Management"])
    
    # Database Explorer tab
    with tabs[0]:
        if st.session_state.selected_schema and st.session_state.selected_table:
            st.header(f"Table: {st.session_state.selected_schema}.{st.session_state.selected_table}")
            
            # Sub-tabs for structure and data
            subtabs = st.tabs(["Data", "Structure"])
            
            # Data sub-tab
            with subtabs[0]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    limit = st.number_input("Limit", min_value=1, max_value=1000, value=100)
                with col2:
                    offset = st.number_input("Offset", min_value=0, value=0)
                
                # Filter options
                with st.expander("Filter and Sort Options"):
                    where_clause = st.text_input("WHERE Clause (without 'WHERE')", "")
                    order_by = st.text_input("ORDER BY Clause (without 'ORDER BY')", "")
                
                # Load button
                if st.button("Load Data"):
                    data_df = get_table_data(
                        st.session_state.selected_schema,
                        st.session_state.selected_table,
                        limit,
                        offset,
                        where_clause,
                        order_by
                    )
                    if data_df is not None and not data_df.empty:
                        st.dataframe(data_df, use_container_width=True)
                    elif data_df is not None and data_df.empty:
                        st.info("No data found for the selected table with the given criteria.")
            
            # Structure sub-tab
            with subtabs[1]:
                structure = get_table_structure(
                    st.session_state.selected_schema,
                    st.session_state.selected_table
                )
                
                if structure:
                    # Columns section
                    st.subheader("Columns")
                    columns_df = pd.DataFrame(
                        structure["columns"],
                        columns=["Column Name", "Data Type", "Nullable", "Default Value"]
                    )
                    # Mark primary keys
                    columns_df["Primary Key"] = columns_df["Column Name"].apply(
                        lambda x: "✓" if x in structure["primary_keys"] else ""
                    )
                    st.dataframe(columns_df, use_container_width=True)
                    
                    # Primary Keys section
                    if structure["primary_keys"]:
                        st.subheader("Primary Keys")
                        st.write(", ".join(structure["primary_keys"]))
                    
                    # Foreign Keys section
                    if structure["foreign_keys"]:
                        st.subheader("Foreign Keys")
                        fk_df = pd.DataFrame(
                            structure["foreign_keys"],
                            columns=["Column", "Foreign Schema", "Foreign Table", "Foreign Column"]
                        )
                        st.dataframe(fk_df, use_container_width=True)
                    
                    # Indexes section
                    if structure["indexes"]:
                        st.subheader("Indexes")
                        indexes_df = pd.DataFrame(
                            structure["indexes"],
                            columns=["Index Name", "Column", "Unique"]
                        )
                        # Convert boolean to checkmark
                        indexes_df["Unique"] = indexes_df["Unique"].apply(lambda x: "✓" if x else "")
                        st.dataframe(indexes_df, use_container_width=True)
        else:
            st.info("Select a schema and table from the sidebar to explore.")
    
    # SQL Editor tab
    with tabs[1]:
        st.header("SQL Query Editor")
        
        # Query history dropdown
        if st.session_state.query_history:
            selected_history = st.selectbox(
                "Query History",
                options=[""] + st.session_state.query_history,
                format_func=lambda x: x[:50] + "..." if len(x) > 50 else x
            )
            query_text = selected_history
        else:
            query_text = ""
        
        # Query editor
        query = st.text_area("Enter SQL Query", value=query_text, height=200)
        
        # Execute button
        if st.button("Execute Query"):
            if query.strip():
                with st.spinner("Executing query..."):
                    result = execute_query(query)
                
                if result["success"]:
                    st.success(result["message"])
                    if result["data"] is not None:
                        st.dataframe(result["data"], use_container_width=True)
                else:
                    st.error(result["message"])
            else:
                st.warning("Please enter a SQL query to execute.")
    
    # Table Management tab
    with tabs[2]:
        st.header("Table Management")
        
        # Sub-tabs for different management options
        mgmt_tabs = st.tabs(["Create Table", "Modify Table", "Drop Table"])
        
        # Create Table tab
        with mgmt_tabs[0]:
            st.subheader("Create New Table")
            
            # Schema selection for new table
            new_table_schema = st.selectbox(
                "Select Schema",
                options=st.session_state.schemas,
                key="new_table_schema"
            )
            
            # Table name for new table
            new_table_name = st.text_input("Table Name")
            
            # Table columns
            columns_container = st.container()
            
            with columns_container:
                st.subheader("Define Columns")
                
                # Initialize columns list in session state if it doesn't exist
                if 'new_table_columns' not in st.session_state:
                    st.session_state.new_table_columns = [
                        {"name": "", "type": "INTEGER", "nullable": True, "primary": False, "default": ""}
                    ]
                
                data_types = [
                    "INTEGER", "BIGINT", "SMALLINT", "DECIMAL", "NUMERIC",
                    "REAL", "DOUBLE PRECISION", "VARCHAR", "CHAR", "TEXT",
                    "BOOLEAN", "DATE", "TIME", "TIMESTAMP", "JSON", "JSONB",
                    "UUID", "BYTEA", "ARRAY"
                ]
                
                for i, col in enumerate(st.session_state.new_table_columns):
                    col1, col2, col3, col4, col5, col6 = st.columns([3, 3, 2, 2, 3, 1])
                    
                    with col1:
                        st.session_state.new_table_columns[i]["name"] = st.text_input(
                            "Name", 
                            value=col["name"], 
                            key=f"col_name_{i}"
                        )
                    
                    with col2:
                        st.session_state.new_table_columns[i]["type"] = st.selectbox(
                            "Type", 
                            options=data_types, 
                            index=data_types.index(col["type"]),
                            key=f"col_type_{i}"
                        )
                    
                    with col3:
                        st.session_state.new_table_columns[i]["nullable"] = st.checkbox(
                            "Nullable", 
                            value=col["nullable"],
                            key=f"col_null_{i}"
                        )
                    
                    with col4:
                        st.session_state.new_table_columns[i]["primary"] = st.checkbox(
                            "Primary", 
                            value=col["primary"],
                            key=f"col_pk_{i}"
                        )
                    
                    with col5:
                        st.session_state.new_table_columns[i]["default"] = st.text_input(
                            "Default", 
                            value=col["default"],
                            key=f"col_default_{i}"
                        )
                    
                    with col6:
                        if i > 0 and st.button("X", key=f"delete_col_{i}"):
                            st.session_state.new_table_columns.pop(i)
                            st.experimental_rerun()
                
                if st.button("Add Column"):
                    st.session_state.new_table_columns.append(
                        {"name": "", "type": "INTEGER", "nullable": True, "primary": False, "default": ""}
                    )
                    st.experimental_rerun()
            
            # Create table button
            if st.button("Create Table"):
                if not new_table_name:
                    st.error("Please enter a table name.")
                elif not new_table_schema:
                    st.error("Please select a schema.")
                elif not any(col["name"] for col in st.session_state.new_table_columns):
                    st.error("Please define at least one column.")
                else:
                    # Generate SQL statements for columns
                    column_statements = []
                    primary_keys = []
                    
                    for col in st.session_state.new_table_columns:
                        if col["name"]:
                            # Basic column definition
                            col_stmt = f"{col['name']} {col['type']}"
                            
                            # NOT NULL constraint
                            if not col["nullable"]:
                                col_stmt += " NOT NULL"
                            
                            # Default value
                            if col["default"]:
                                col_stmt += f" DEFAULT {col['default']}"
                            
                            # Add to column statements
                            column_statements.append(col_stmt)
                            
                            # Collect primary keys
                            if col["primary"]:
                                primary_keys.append(col["name"])
                    
                    # Add primary key constraint if any
                    if primary_keys:
                        column_statements.append(f"PRIMARY KEY ({', '.join(primary_keys)})")
                    
                    # Create the table
                    result = create_table(new_table_schema, new_table_name, column_statements)
                    
                    if result["success"]:
                        st.success(result["message"])
                        # Clear the form
                        st.session_state.new_table_columns = [
                            {"name": "", "type": "INTEGER", "nullable": True, "primary": False, "default": ""}
                        ]
                        # Refresh tables list
                        get_tables(new_table_schema)
                    else:
                        st.error(result["message"])
        
        # Modify Table tab
        with mgmt_tabs[1]:
            if st.session_state.selected_schema and st.session_state.selected_table:
                st.subheader(f"Modify Table: {st.session_state.selected_schema}.{st.session_state.selected_table}")
                
                modify_tabs = st.tabs(["Add Column", "Rename Table", "Add Index"])
                
                # Add Column sub-tab
                with modify_tabs[0]:
                    with st.form("add_column_form"):
                        col_name = st.text_input("Column Name")
                        col_type = st.selectbox("Data Type", [
                            "INTEGER", "BIGINT", "SMALLINT", "DECIMAL", "NUMERIC",
                            "REAL", "DOUBLE PRECISION", "VARCHAR", "CHAR", "TEXT",
                            "BOOLEAN", "DATE", "TIME", "TIMESTAMP", "JSON", "JSONB",
                            "UUID", "BYTEA", "ARRAY"
                        ])
                        nullable = st.checkbox("Nullable", value=True)
                        default_value = st.text_input("Default Value")
                        
                        submit = st.form_submit_button("Add Column")
                        
                        if submit:
                            if not col_name:
                                st.error("Please enter a column name")
                            else:
                                # Build query
                                query = f"ALTER TABLE {st.session_state.selected_schema}.{st.session_state.selected_table} "
                                query += f"ADD COLUMN {col_name} {col_type}"
                                if not nullable:
                                    query += " NOT NULL"
                                if default_value:
                                    query += f" DEFAULT {default_value}"
                                query += ";"
                                
                                result = execute_query(query)
                                if result["success"]:
                                    st.success(result["message"])
                                else:
                                    st.error(result["message"])
                
                # Rename Table sub-tab
                with modify_tabs[1]:
                    with st.form("rename_table_form"):
                        new_name = st.text_input("New Table Name")
                        submit = st.form_submit_button("Rename Table")
                        
                        if submit:
                            if not new_name:
                                st.error("Please enter a new table name")
                            else:
                                query = f"ALTER TABLE {st.session_state.selected_schema}.{st.session_state.selected_table} "
                                query += f"RENAME TO {new_name};"
                                
                                result = execute_query(query)
                                if result["success"]:
                                    st.success(result["message"])
                                    # Refresh tables list
                                    get_tables(st.session_state.selected_schema)
                                    # Update selected table
                                    st.session_state.selected_table = new_name
                                else:
                                    st.error(result["message"])
                
                # Add Index sub-tab
                with modify_tabs[2]:
                    with st.form("add_index_form"):
                        # Get table columns
                        structure = get_table_structure(
                            st.session_state.selected_schema,
                            st.session_state.selected_table
                        )
                        
                        if structure:
                            columns = [col[0] for col in structure["columns"]]
                            
                            index_name = st.text_input("Index Name")
                            index_columns = st.multiselect("Select Columns", options=columns)
                            unique = st.checkbox("Unique Index", value=False)
                            
                            submit = st.form_submit_button("Create Index")
                            
                            if submit:
                                if not index_name:
                                    st.error("Please enter an index name")
                                elif not index_columns:
                                    st.error("Please select at least one column")
                                else:
                                    query = f"CREATE "
                                    if unique:
                                        query += "UNIQUE "
                                    query += f"INDEX {index_name} ON {st.session_state.selected_schema}.{st.session_state.selected_table} "
                                    query += f"({', '.join(index_columns)});"
                                    
                                    result = execute_query(query)
                                    if result["success"]:
                                        st.success(result["message"])
                                    else:
                                        st.error(result["message"])
            else:
                st.info("Select a schema and table from the sidebar to modify.")
        
        # Drop Table tab
        with mgmt_tabs[2]:
            if st.session_state.selected_schema and st.session_state.selected_table:
                st.subheader(f"Drop Table: {st.session_state.selected_schema}.{st.session_state.selected_table}")
                
                st.warning("⚠️ Warning: Dropping a table will permanently delete all its data. This action cannot be undone.")
                
                confirm_name = st.text_input(f"Type '{st.session_state.selected_table}' to confirm deletion")
                
                if st.button("Drop Table"):
                    if confirm_name == st.session_state.selected_table:
                        query = f"DROP TABLE {st.session_state.selected_schema}.{st.session_state.selected_table};"
                        
                        result = execute_query(query)
                        if result["success"]:
                            st.success(result["message"])
                            # Refresh tables list
                            get_tables(st.session_state.selected_schema)
                            # Clear selected table
                            st.session_state.selected_table = None
                        else:
                            st.error(result["message"])
                    else:
                        st.error("Table name doesn't match. Please type the correct table name to confirm.")
            else:
                st.info("Select a schema and table from the sidebar to drop.")
else:
    st.info("Please connect to a PostgreSQL database using the sidebar.")