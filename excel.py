import pandas as pd
from io import BytesIO

def create_excel_workbook(sheets_dict):
    """Creates a styled Excel workbook and returns it as a BytesIO buffer."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df_sheet in sheets_dict.items():
            df_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            # Future Excel-specific styling can be added here
    buffer.seek(0)
    return buffer
