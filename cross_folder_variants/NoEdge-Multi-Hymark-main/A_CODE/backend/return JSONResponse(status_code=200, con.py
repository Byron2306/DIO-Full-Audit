return JSONResponse(status_code=200, content=response_payload)

    except Exception as e:
        print(f"[Backend Upload Endpoint Crash] {e}")
        return JSONResponse(
            status_code=500,
                content={
                    "success": False,
                    "detail": f"Server extraction engine fault: {str(e)}",
                },
            ),
        )

