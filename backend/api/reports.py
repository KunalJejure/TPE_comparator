from fastapi import APIRouter, Query, Response
from typing import Optional, List
import csv
import io
from backend.database import get_comparison_stats, get_all_comparisons, get_comparison_result

router = APIRouter()

@router.get("/history/{id}")
async def get_history_result(id: int):
    """Get the full result JSON for a specific comparison."""
    result = get_comparison_result(id)
    if not result:
         return Response(content="{}", media_type="application/json")
    
    return Response(content=result, media_type="application/json")

@router.get("/stats")
async def get_stats():
    """Get aggregated statistics for the reports dashboard."""
    return get_comparison_stats()

@router.get("/history_full")
async def get_history_full(
    status: Optional[str] = Query(None, description="Filter by status (e.g. PASS, FAIL, CHANGES FOUND)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get full history with optional filtering."""
    return get_all_comparisons(status_filter=status, start_date=start_date, end_date=end_date)

@router.get("/export")
async def export_history(
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Export the filtered history as a CSV file."""
    data = get_all_comparisons(status_filter=status, start_date=start_date, end_date=end_date)
    
    if not data:
        # Return empty CSV
        return Response(content="No data found", media_type="text/csv")
        
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    headers = ["ID", "Timestamp", "Original Filename", "Revised Filename", "Total Pages", "Status", "Report URL"]
    writer.writerow(headers)
    
    # Rows
    for row in data:
        writer.writerow([
            row["id"],
            row["timestamp"],
            row["original_filename"],
            row["revised_filename"],
            row["total_pages"],
            row["status"],
            row["report_url"] or ""
        ])
        
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=comparison_history.csv"}
    )
