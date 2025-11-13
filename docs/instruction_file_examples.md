# Instruction File Examples for Different Project Types

**Version**: 1.0
**Last Updated**: 2025-11-13
**Purpose**: Complete examples showing how to customize instruction files for various project types

## Table of Contents

1. [Overview](#overview)
2. [Example 1: Financial Application](#example-1-financial-application)
3. [Example 2: Game Development](#example-2-game-development)
4. [Example 3: Web API Service](#example-3-web-api-service)
5. [Example 4: Data Processing Tool](#example-4-data-processing-tool)
6. [Example 5: Web UI Enhancement](#example-5-web-ui-enhancement)
7. [Comparison Matrix](#comparison-matrix)

---

## Overview

This document provides complete examples of instruction file customization for different project types. Each example shows:

- Project characteristics
- Recommended roles
- Domain-specific guidance
- Technology-specific patterns
- Common pitfalls for that domain
- Complete workflow phases

Use these as reference when creating instruction files for similar projects.

---

## Example 1: Financial Application

### Project: Credit Card Balance Transfer Calculator

**Type**: CLI Application
**Domain**: Financial/Accounting
**Tech Stack**: Python
**Complexity**: Medium (precise calculations required)

### Role Selection

**Phase 1 - Requirements**:
- Product Manager (lead)
- Business Analyst
- *Optional: Financial Domain Expert for complex financial products*

**Phase 2 - Planning**:
- Engineering Manager (lead)
- Technical Lead

**Phase 3 - Implementation**:
- Lead Developer (lead)
- Code Reviewer

### Key Customizations

#### Domain-Specific Guidance (Financial)

```markdown
## Financial Calculation Guidance

### CRITICAL: Decimal Precision

**Always use Decimal, never float:**
```python
from decimal import Decimal, ROUND_HALF_UP

# ✅ CORRECT - No rounding errors
principal = Decimal("10000.00")
apr = Decimal("0.185")
monthly_rate = apr / Decimal("12")
interest = principal * monthly_rate
# Result: Exactly 154.17 (rounded to 2 places)

# ❌ WRONG - Float introduces errors
principal = 10000.00
apr = 0.185
monthly_rate = apr / 12
interest = principal * monthly_rate
# Result: 154.166666666667 → 154.17 (but intermediate errors accumulate)
```

**Why this matters:**
- Float errors accumulate over many calculations
- Financial results must match exactly what users expect
- Regulatory compliance may require specific precision

### Interest Calculation Formulas

**Simple Interest:**
```
I = P × r × t

Where:
- I = Interest (Decimal)
- P = Principal (Decimal)
- r = Annual rate (Decimal, e.g., 0.185 for 18.5%)
- t = Time in years (Decimal)
```

**Compound Interest (Monthly):**
```
A = P × (1 + r/12)^n
I = A - P

Where:
- A = Final amount (Decimal)
- P = Principal (Decimal)
- r = Annual rate (Decimal)
- n = Number of months (int)
- I = Total interest paid (Decimal)
```

**Monthly Payment Calculation:**
```
M = P × [r(1+r)^n] / [(1+r)^n - 1]

Where:
- M = Monthly payment (Decimal)
- P = Principal (Decimal)
- r = Monthly interest rate (annual_rate / 12)
- n = Number of payments (int)
```

### Input Validation Requirements

**For Credit Card Calculator:**
```python
def validate_inputs(debt, current_apr, promo_apr, monthly_payment):
    """Validate all financial inputs"""
    errors = []

    # Debt validation
    if debt <= Decimal("0"):
        errors.append("Debt must be positive")
    if debt > Decimal("1000000"):  # Sanity check
        errors.append("Debt exceeds reasonable limit")

    # APR validation
    if current_apr < Decimal("0") or current_apr > Decimal("1"):
        errors.append("Current APR must be between 0% and 100%")
    if promo_apr < Decimal("0") or promo_apr > Decimal("1"):
        errors.append("Promo APR must be between 0% and 100%")

    # Payment validation
    if monthly_payment <= Decimal("0"):
        errors.append("Monthly payment must be positive")

    # Logical validation
    min_payment = (debt * current_apr / Decimal("12")) * Decimal("1.01")
    if monthly_payment < min_payment:
        errors.append(f"Payment too low - barely covers interest")

    return errors
```

### Edge Cases for Financial Calculations

1. **Zero Interest Scenarios**:
   - Promo APR = 0%
   - Should return simple total_debt / monthly_payment calculation
   - No interest accumulation

2. **Payment Exactly Equals Interest**:
   - Monthly payment = (debt × APR) / 12
   - Debt never decreases (infinite payoff time)
   - Must warn user or reject as invalid

3. **Very Small Debt**:
   - Debt < $10
   - May pay off in one payment
   - Division by zero risks in some formulas

4. **Very Large Timeframes**:
   - Payoff > 30 years
   - Probably indicates payment too low
   - Should warn user

5. **Negative Results**:
   - Can happen with calculation errors
   - Should never display to user
   - Indicates a bug to fix

### Common Financial Domain Pitfalls

**Precision Errors:**
- ⚠️ Don't use float for any currency amount
- ⚠️ Don't forget to round final display values to 2 decimals
- ⚠️ Don't mix Decimal and float (converts to float)
- ✅ Do use Decimal throughout entire calculation chain
- ✅ Do round only for final display, not intermediate calculations

**Formula Misunderstandings:**
- ⚠️ Don't confuse APR (annual) with monthly rate
- ⚠️ Don't forget to convert percentage to decimal (18.5% → 0.185)
- ⚠️ Don't use 365-day year for month calculations (use 12 months)
- ✅ Do clearly document which formula you're using
- ✅ Do verify calculations against known test cases

**Edge Case Handling:**
- ⚠️ Don't assume all inputs are valid
- ⚠️ Don't let users enter impossible scenarios
- ⚠️ Don't crash on division by zero
- ✅ Do validate all inputs before calculation
- ✅ Do provide clear error messages
- ✅ Do handle edge cases explicitly

### Testing Requirements for Financial Code

**Unit Tests Must Include:**
- Known calculation test cases (verified by hand or calculator)
- Zero interest scenarios
- Edge cases (very small/large values)
- Precision verification (exact decimal matches)

**Example Test:**
```python
def test_compound_interest_known_value():
    """Test with a known correct result"""
    principal = Decimal("10000.00")
    annual_rate = Decimal("0.18")
    months = 12

    result = calculate_compound_interest(principal, annual_rate, months)

    # Verified correct answer: $1956.18
    expected = Decimal("1956.18")
    assert result == expected, f"Expected {expected}, got {result}"
```
```

#### Technology-Specific Patterns (Python)

```markdown
## Python Code Standards for Financial Applications

### Required Imports
```python
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple
```

### Function Signature Pattern
```python
def calculate_scenario(
    debt: Decimal,
    apr: Decimal,
    monthly_payment: Decimal
) -> Dict[str, Decimal]:
    """
    Calculate payoff scenario for given parameters.

    Args:
        debt: Initial debt amount (Decimal)
        apr: Annual Percentage Rate as decimal (e.g., 0.185 for 18.5%)
        monthly_payment: Monthly payment amount (Decimal)

    Returns:
        Dictionary with:
        - 'months_to_payoff': Number of months (int)
        - 'total_interest': Total interest paid (Decimal)
        - 'total_paid': Total amount paid (Decimal)

    Raises:
        ValueError: If payment is too low to cover interest
    """
    # Implementation here
```

### Rounding Pattern
```python
def round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places using banker's rounding"""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### Output Format Pattern
```python
def format_currency(amount: Decimal) -> str:
    """Format Decimal as currency string"""
    return f"${amount:,.2f}"

# Usage:
print(f"Total interest: {format_currency(total_interest)}")
# Output: "Total interest: $1,956.18"
```
```

### Workflow Phases for Financial Project

**Phase 1: Requirements (Turns 1-10)**
```markdown
**Phase 1: Initial Analysis** (Turn 1-2)
- [ ] Read USER_REQUEST.md
- [ ] Identify what financial calculations are needed
- [ ] Note any formulas mentioned or implied
- [ ] List initial questions about calculation methods
- Exit criteria: Understand core financial problem

**Phase 2: Formula Clarification** (Turn 3-5)
- [ ] Discuss with Business Analyst which formulas to use
- [ ] Determine precision requirements (decimals)
- [ ] Identify edge cases specific to finance domain
- [ ] Decide if clarification needed on calculation method
- Exit criteria: Formula approach is clear

**Phase 3: PRD Creation** (Turn 6-10)
- [ ] Write PRD with detailed formula specifications
- [ ] Document all financial validation rules
- [ ] Define edge cases and error handling
- [ ] Include test cases with known results
- [ ] Get Business Analyst approval
- Exit criteria: PRD complete and approved
```

---

## Example 2: Game Development

### Project: Snake Game (Pygame)

**Type**: Desktop Game
**Domain**: Gaming
**Tech Stack**: Python + Pygame
**Complexity**: Medium (game loop, collision detection, state management)

### Role Selection

**Phase 1 - Requirements**:
- Product Manager (acting as Game Designer lead)
- Gaming Domain Expert or UX Designer

**Phase 2 - Planning**:
- Engineering Manager (lead)
- Technical Lead

**Phase 3 - Implementation**:
- Lead Developer (lead)
- Code Reviewer
- *Optional: QA Engineer for gameplay testing*

### Key Customizations

#### Domain-Specific Guidance (Gaming)

```markdown
## Game Development Guidance

### Core Game Loop Pattern

**Every game needs a main loop:**
```python
import pygame

def main():
    clock = pygame.time.Clock()
    FPS = 60  # Target frame rate

    running = True
    while running:
        # 1. Handle events (input)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 2. Update game state (logic)
        dt = clock.tick(FPS) / 1000.0  # Delta time in seconds
        update_game(dt)

        # 3. Render (draw)
        draw_game()

    pygame.quit()
```

**Why this matters:**
- Separates input, logic, and rendering
- Frame-rate independent movement via delta time
- Predictable execution order

### Frame-Rate Independence

**CRITICAL: Use delta time for all movement:**
```python
# ✅ CORRECT - Frame-rate independent
def update_snake(dt):
    """dt: Time elapsed since last frame in seconds"""
    self.x += self.velocity_x * dt
    self.y += self.velocity_y * dt

# ❌ WRONG - Tied to frame rate
def update_snake():
    self.x += self.velocity_x  # Moves faster on faster computers
    self.y += self.velocity_y
```

**Why this matters:**
- Game speed should be same on all computers
- 30 FPS vs 60 FPS shouldn't change gameplay
- Professional standard for game development

### Collision Detection

**Bounding Box (Rectangle) Collision:**
```python
def check_collision(obj1, obj2):
    """Check if two rectangles overlap"""
    return (obj1.x < obj2.x + obj2.width and
            obj1.x + obj1.width > obj2.x and
            obj1.y < obj2.y + obj2.height and
            obj1.y + obj1.height > obj2.y)
```

**Snake Self-Collision:**
```python
def check_self_collision(snake_segments):
    """Check if snake head collides with body"""
    head = snake_segments[0]
    body = snake_segments[1:]

    for segment in body:
        if head.x == segment.x and head.y == segment.y:
            return True
    return False
```

**Grid-Based Collision (for Snake game):**
```python
# Since Snake moves on a grid, use grid coordinates
def check_food_collision(snake_head, food):
    """Check if snake head is on same grid cell as food"""
    return (snake_head.grid_x == food.grid_x and
            snake_head.grid_y == food.grid_y)
```

### Game State Management

**State Machine Pattern:**
```python
class GameState:
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"

class Game:
    def __init__(self):
        self.state = GameState.MENU

    def update(self, dt):
        if self.state == GameState.MENU:
            self.update_menu()
        elif self.state == GameState.PLAYING:
            self.update_gameplay(dt)
        elif self.state == GameState.PAUSED:
            self.update_pause()
        elif self.state == GameState.GAME_OVER:
            self.update_game_over()
```

### Input Handling for Snake Game

**Direction Change Logic:**
```python
def handle_input(self, event):
    """Handle keyboard input for direction changes"""
    if event.type == pygame.KEYDOWN:
        # Can't reverse directly (snake would collide with itself)
        if event.key == pygame.K_UP and self.direction != "DOWN":
            self.direction = "UP"
        elif event.key == pygame.K_DOWN and self.direction != "UP":
            self.direction = "DOWN"
        elif event.key == pygame.K_LEFT and self.direction != "RIGHT":
            self.direction = "LEFT"
        elif event.key == pygame.K_RIGHT and self.direction != "LEFT":
            self.direction = "RIGHT"
```

### Game Design Specifications

**Requirements Should Include:**

**Player Controls:**
- Input method: Keyboard arrow keys
- Response time: Immediate (no lag)
- Movement: Grid-based (not smooth pixel-by-pixel)

**Game Mechanics:**
- Snake moves continuously in current direction
- Speed: [X] grid cells per second
- Food spawns at random grid positions
- Eating food increases length by 1 segment
- Collision with wall or self = game over

**Difficulty Curve:**
- Level 1: Speed = 4 cells/sec
- Each food eaten: Speed += 0.1 cells/sec
- Maximum speed: 10 cells/sec

**Visual Feedback:**
- Snake: Green rectangles
- Food: Red circle
- Score displayed in top-left
- Game over message when collision

**Audio Feedback (if applicable):**
- Eating food: "munch" sound
- Game over: "crash" sound
- Background music: Optional

### Common Game Development Pitfalls

**Frame Rate Issues:**
- ⚠️ Don't tie game logic to rendering
- ⚠️ Don't use sleep() to control frame rate
- ⚠️ Don't forget delta time in movement
- ✅ Do use clock.tick(FPS) to limit frame rate
- ✅ Do pass delta time to all update functions

**Collision Detection:**
- ⚠️ Don't check collision before updating position
- ⚠️ Don't forget to check self-collision
- ⚠️ Don't use pixel-perfect collision for grid games
- ✅ Do use appropriate collision method for your game type
- ✅ Do test collision detection thoroughly

**State Management:**
- ⚠️ Don't mix game states (playing + menu at same time)
- ⚠️ Don't forget to pause game logic when paused
- ⚠️ Don't reset game state when just pausing
- ✅ Do use state machine pattern
- ✅ Do separate game logic from rendering

**Input Handling:**
- ⚠️ Don't allow impossible moves (reversing in Snake)
- ⚠️ Don't queue too many inputs (causes lag feeling)
- ⚠️ Don't check keyboard state every frame (use events)
- ✅ Do validate direction changes
- ✅ Do handle multiple key presses gracefully

### Edge Cases for Games

1. **Window Resize/Close:**
   - What happens if player resizes window mid-game?
   - Graceful shutdown on window close

2. **Pause/Unpause:**
   - Game logic must actually stop
   - Timer must pause
   - Resume should feel seamless

3. **Very High Scores:**
   - Score display fits on screen at 9999+?
   - Number doesn't overflow

4. **Rapid Input:**
   - Player presses multiple keys very quickly
   - Only process valid direction changes

5. **Food Spawn Position:**
   - Food should never spawn on snake body
   - Handle case where grid is almost full
```

#### Technology-Specific Patterns (Pygame)

```markdown
## Pygame Code Standards

### Project Structure
```
snake_game/
├── main.py           # Entry point, game loop
├── game.py           # Game class, state management
├── snake.py          # Snake class
├── food.py           # Food class
├── constants.py      # Game constants (colors, sizes, speeds)
└── utils.py          # Helper functions
```

### Constants Pattern
```python
# constants.py
# Window
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 60

# Grid
GRID_SIZE = 20  # Size of each grid cell in pixels
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE

# Colors (RGB)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Game
INITIAL_SPEED = 4  # Grid cells per second
SPEED_INCREMENT = 0.1
MAX_SPEED = 10
```

### Snake Class Pattern
```python
# snake.py
import pygame
from constants import GRID_SIZE, GREEN

class Snake:
    def __init__(self, start_x, start_y):
        self.segments = [(start_x, start_y)]  # List of (x, y) tuples
        self.direction = "RIGHT"
        self.grow_pending = False

    def update(self, dt, speed):
        """Move snake based on current direction"""
        # Calculate move based on speed and delta time
        # ... implementation

    def grow(self):
        """Mark that snake should grow on next update"""
        self.grow_pending = True

    def draw(self, surface):
        """Draw snake on the given surface"""
        for x, y in self.segments:
            rect = pygame.Rect(
                x * GRID_SIZE,
                y * GRID_SIZE,
                GRID_SIZE,
                GRID_SIZE
            )
            pygame.draw.rect(surface, GREEN, rect)
```
```

---

## Example 3: Web API Service

### Project: REST API for Task Management

**Type**: Web API/Service
**Domain**: General/Productivity
**Tech Stack**: Python + FastAPI + PostgreSQL
**Complexity**: Medium-High (CRUD operations, authentication, database)

### Key Customizations

#### Domain-Specific Guidance (Web API)

```markdown
## REST API Development Guidance

### API Design Principles

**RESTful Resource Naming:**
```
GET    /api/tasks              # List all tasks
GET    /api/tasks/{id}         # Get specific task
POST   /api/tasks              # Create new task
PUT    /api/tasks/{id}         # Update entire task
PATCH  /api/tasks/{id}         # Update partial task
DELETE /api/tasks/{id}         # Delete task

# ✅ GOOD - Resource naming
GET /api/users
GET /api/users/{id}/tasks

# ❌ BAD - Action in URL
GET /api/getTasks
POST /api/createTask
```

### HTTP Status Codes

**Use appropriate status codes:**
```python
from fastapi import HTTPException, status

# Success responses
return task, status.HTTP_200_OK          # GET success
return task, status.HTTP_201_CREATED     # POST success
return None, status.HTTP_204_NO_CONTENT  # DELETE success

# Client error responses
raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid input")
raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
raise HTTPException(status.HTTP_403_FORBIDDEN, "No permission")
raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
raise HTTPException(status.HTTP_409_CONFLICT, "Task already exists")

# Server error responses
raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Server error")
```

### Request/Response Models (Pydantic)

**Separate Input and Output Models:**
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# Input model (what client sends)
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[datetime] = None
    priority: int = Field(1, ge=1, le=5)

# Output model (what API returns)
class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    priority: int
    created_at: datetime
    updated_at: datetime
    user_id: int

    class Config:
        orm_mode = True  # Allow from ORM objects
```

### Authentication Pattern

**JWT Token Authentication:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Validate JWT token and return current user"""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

        user = get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

# Usage in endpoint:
@app.get("/api/tasks")
async def list_tasks(current_user: User = Depends(get_current_user)):
    """List tasks for current user"""
    return get_tasks_for_user(current_user.id)
```

### Error Handling Pattern

**Consistent Error Responses:**
```python
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    detail: str
    code: str
    timestamp: datetime

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            code=exc.status_code,
            timestamp=datetime.utcnow()
        ).dict()
    )
```

### Common API Development Pitfalls

**Security:**
- ⚠️ Don't expose internal errors to clients
- ⚠️ Don't return passwords in API responses
- ⚠️ Don't skip input validation
- ⚠️ Don't allow SQL injection via unvalidated inputs
- ✅ Do use Pydantic models for validation
- ✅ Do sanitize all user inputs
- ✅ Do use prepared statements/ORM

**Performance:**
- ⚠️ Don't do N+1 queries
- ⚠️ Don't return entire database in one request
- ⚠️ Don't forget to add database indexes
- ✅ Do implement pagination
- ✅ Do use eager loading for related data
- ✅ Do add response caching where appropriate

**Versioning:**
- ⚠️ Don't break existing clients with changes
- ⚠️ Don't forget to version your API
- ✅ Do use `/api/v1/` in URLs
- ✅ Do maintain backwards compatibility
```

---

## Example 4: Data Processing Tool

### Project: CSV Data Cleaner and Analyzer

**Type**: CLI Tool
**Domain**: Data Processing
**Tech Stack**: Python + Pandas
**Complexity**: Medium

### Key Customizations

```markdown
## Data Processing Guidance

### Data Validation Patterns

**Input Validation:**
```python
import pandas as pd
from pathlib import Path

def validate_csv_file(file_path: str) -> tuple[bool, str]:
    """Validate CSV file exists and is readable"""
    path = Path(file_path)

    if not path.exists():
        return False, f"File not found: {file_path}"

    if not path.is_file():
        return False, f"Not a file: {file_path}"

    if path.suffix.lower() != '.csv':
        return False, f"Not a CSV file: {file_path}"

    try:
        # Try reading first few rows
        pd.read_csv(file_path, nrows=5)
        return True, "Valid"
    except Exception as e:
        return False, f"Cannot read CSV: {str(e)}"
```

### Data Cleaning Patterns

**Handle Missing Values:**
```python
def clean_missing_values(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """Clean missing values based on strategy"""
    if strategy == "drop":
        return df.dropna()
    elif strategy == "fill_zero":
        return df.fillna(0)
    elif strategy == "fill_mean":
        return df.fillna(df.mean())
    elif strategy == "fill_forward":
        return df.fillna(method='ffill')
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
```

**Data Type Conversion:**
```python
def convert_column_types(df: pd.DataFrame, type_map: dict) -> pd.DataFrame:
    """Convert columns to specified types"""
    for column, dtype in type_map.items():
        if column not in df.columns:
            raise ValueError(f"Column not found: {column}")

        try:
            if dtype == "numeric":
                df[column] = pd.to_numeric(df[column], errors='coerce')
            elif dtype == "datetime":
                df[column] = pd.to_datetime(df[column], errors='coerce')
            elif dtype == "string":
                df[column] = df[column].astype(str)
        except Exception as e:
            raise ValueError(f"Cannot convert {column} to {dtype}: {e}")

    return df
```

### Common Data Processing Pitfalls

**Memory Management:**
- ⚠️ Don't load entire large file into memory
- ⚠️ Don't create unnecessary copies of dataframes
- ✅ Do use chunked reading for large files
- ✅ Do use inplace operations when possible

**Data Quality:**
- ⚠️ Don't assume all data is clean
- ⚠️ Don't ignore encoding issues
- ✅ Do validate data at each step
- ✅ Do specify encoding explicitly (utf-8, latin-1, etc.)

**Error Handling:**
- ⚠️ Don't let one bad row crash entire processing
- ⚠️ Don't silently skip errors
- ✅ Do log errors and continue
- ✅ Do provide summary of issues found
```

---

## Example 5: Web UI Enhancement

### Project: Add Web Interface to Existing CLI Calculator

**Type**: Web UI Addon
**Domain**: Varies (example: Financial)
**Tech Stack**: FastAPI + React + Tailwind
**Complexity**: Medium-High (full-stack integration)

### Key Customizations

```markdown
## Web UI Enhancement Guidance

### Integration Pattern

**DO NOT modify existing code:**
```python
# backend/main.py

# Import existing calculator functions
import sys
sys.path.append('../')  # Adjust to reach existing code
from calculator import calculate_scenario_a, calculate_scenario_b

# Use existing functions directly
@app.post("/api/calculate")
async def calculate(request: CalculatorRequest):
    # Call existing code (DO NOT DUPLICATE LOGIC)
    result_a = calculate_scenario_a(
        request.debt,
        request.current_apr,
        request.monthly_payment
    )

    result_b = calculate_scenario_b(
        request.debt,
        request.promo_apr,
        request.monthly_payment,
        request.promo_months
    )

    return {
        "scenario_a": result_a,
        "scenario_b": result_b
    }
```

### Validation Strategy

**Validate on Both Client and Server:**
```javascript
// Frontend validation (user experience)
function validateInput(debt, apr, payment) {
    const errors = [];

    if (debt <= 0) errors.push("Debt must be positive");
    if (apr < 0 || apr > 1) errors.push("APR must be 0-100%");
    if (payment <= 0) errors.push("Payment must be positive");

    return errors;
}
```

```python
# Backend validation (security - NEVER trust client)
class CalculatorRequest(BaseModel):
    debt: Decimal = Field(gt=0, description="Must be positive")
    current_apr: Decimal = Field(ge=0, le=1, description="0 to 1")
    promo_apr: Decimal = Field(ge=0, le=1, description="0 to 1")
    monthly_payment: Decimal = Field(gt=0, description="Must be positive")
```

### Data Precision Handling

**Frontend must preserve backend precision:**
```javascript
// ✅ CORRECT - Use string to preserve Decimal precision
const requestData = {
    debt: debtInput.toString(),  // "10000.00"
    current_apr: (aprInput / 100).toString(),  // Convert % to decimal
    monthly_payment: paymentInput.toString()
};

// ❌ WRONG - Number loses precision
const requestData = {
    debt: parseFloat(debtInput),  // May introduce errors
    current_apr: aprInput / 100
};
```

### Common Web UI Enhancement Pitfalls

**Integration:**
- ⚠️ Don't duplicate calculation logic in JavaScript
- ⚠️ Don't modify existing application code
- ⚠️ Don't forget to convert units (% to decimal, etc.)
- ✅ Do import and call existing functions
- ✅ Do verify results match terminal app exactly

**CORS:**
- ⚠️ Don't forget CORS configuration
- ⚠️ Don't use allow_origins=["*"] in production
- ✅ Do configure specific origins
- ✅ Do test cross-origin requests

**Precision:**
- ⚠️ Don't use Number for currency in JavaScript
- ⚠️ Don't round before sending to backend
- ✅ Do use strings for Decimal values
- ✅ Do let backend handle all calculations
```

---

## Comparison Matrix

| Aspect | Financial App | Game | Web API | Data Tool | Web UI Addon |
|--------|---------------|------|---------|-----------|--------------|
| **Primary Concern** | Precision | Frame rate | Security | Memory | Integration |
| **Critical Technology** | Decimal | Pygame/Delta time | Pydantic/JWT | Pandas | FastAPI+React |
| **Testing Focus** | Calculation accuracy | Gameplay feel | API contracts | Data quality | Result matching |
| **Common Pitfall** | Float errors | Frame-rate coupling | No validation | Memory overflow | Logic duplication |
| **Edge Cases** | Zero interest, infinite payoff | Pause/resume, grid full | Auth expiry, not found | Encoding, missing values | CORS, precision loss |
| **Performance Concern** | Formula complexity | 60 FPS | N+1 queries | Large files | API response time |

---

## Quick Reference: Choosing Example

**Your Project Is...**

**Financial/Accounting?**
→ Use Example 1 (Financial Application)
- Focus on Decimal precision
- Include calculation formulas
- Document edge cases for money

**Game/Interactive?**
→ Use Example 2 (Game Development)
- Focus on game loop and delta time
- Include collision detection
- Document game mechanics clearly

**Web Service/API?**
→ Use Example 3 (Web API Service)
- Focus on REST patterns
- Include authentication
- Document request/response models

**Data Processing/Analysis?**
→ Use Example 4 (Data Processing Tool)
- Focus on data validation
- Include cleaning patterns
- Document chunking for large data

**Adding Web UI to Existing Code?**
→ Use Example 5 (Web UI Enhancement)
- Focus on integration patterns
- Include both frontend and backend
- Document precision handling

---

**Related Documentation**:
- `instruction_file_creation_guide.md` - Overall methodology
- `instruction_file_templates.md` - Blank templates with variables
- `instruction_file_generator.md` - Interactive generation script
- `role_authority_patterns.md` - Decision-making patterns
