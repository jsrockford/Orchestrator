# USER_REQUEST.md Guidelines

**Purpose**: This document explains how to write an effective USER_REQUEST.md file that helps AI models create comprehensive Product Requirements Documents (PRDs).

**Last Updated**: 2025-11-13

---

## What is USER_REQUEST.md?

USER_REQUEST.md is the **starting point** for every Orchestrator project. It's a simple markdown file where you describe what you want to build. The AI models read this file to understand your needs and create a detailed PRD.

**Key Concept**: Think of USER_REQUEST.md as your initial project pitch or requirements gathering session - but in written form.

---

## Why This File Matters

The quality of your USER_REQUEST.md directly impacts:

1. **PRD Quality**: Better input = better requirements documentation
2. **Clarification Rounds**: Clear requests often get a PRD in one session
3. **Implementation Success**: Complete requirements lead to better code
4. **Time Efficiency**: Good USER_REQUEST.md saves hours of back-and-forth

---

## Core Principle: Be Specific, Not Technical

**Good USER_REQUEST.md:**
- Describes WHAT you want and WHY
- Provides concrete examples
- Explains the problem you're solving
- Shows what success looks like

**Poor USER_REQUEST.md:**
- Specifies HOW to implement (that's for later phases)
- Uses vague language ("make it good", "should be fast")
- Assumes AI knows your domain
- Lacks examples or context

---

## Recommended Structure

Use this structure as a starting point (adapt as needed):

```markdown
# User Request - [Project Name]

## Problem Statement
[What problem are you trying to solve? Why does this matter?]

## What I Need
[What should the software do? What are the main features/capabilities?]

## Example Use Case
[Walk through a concrete example of someone using this. Step-by-step.]

## Inputs
[What information/data will users provide?]

## Expected Outputs
[What should the system produce? What should results look like?]

## Important Considerations
[Any constraints, preferences, standards, or special requirements]
```

---

## Section-by-Section Guide

### 1. Problem Statement

**Purpose**: Explain WHY this project matters.

**What to Include:**
- The pain point or need you're addressing
- Who is affected by this problem
- What happens now (without this solution)
- Why existing solutions don't work

**Example - Good:**
```markdown
## Problem Statement

I'm losing track of my monthly spending and frequently overdraw my account.
I need to see where my money is going so I can make better decisions.
Existing budgeting apps are too complex - I just need something simple that
shows income vs. expenses.
```

**Example - Poor:**
```markdown
## Problem Statement

I need a budget tracker.
```

**Why the first is better**: Provides context, explains the pain, mentions existing solutions, defines "simple" as a requirement.

---

### 2. What I Need

**Purpose**: Describe the main features and capabilities.

**What to Include:**
- Core functionality (what must it do?)
- Key features (list them explicitly)
- User-facing capabilities
- Scope boundaries (what it WON'T do)

**Example - Good:**
```markdown
## What I Need

A simple budget tracking tool that:
- Lets me enter my monthly income once per month
- Allows me to record expenses with amount, category, and date
- Shows me how much of my budget remains
- Warns me when I'm close to overspending
- Displays spending breakdown by category

Out of scope (not needed):
- Multiple users or accounts
- Investment tracking
- Bill reminders
- Mobile app (web-based is fine)
```

**Example - Poor:**
```markdown
## What I Need

A budget tracker with all the features.
```

**Why the first is better**: Specific features listed, clear scope, explicitly mentions what's NOT needed.

---

### 3. Example Use Case

**Purpose**: Show how someone would actually use this.

**What to Include:**
- Step-by-step walkthrough of typical use
- Specific data examples (not placeholders)
- What the user sees at each step
- The end result or outcome

**Example - Good:**
```markdown
## Example Use Case

**Scenario: Sarah tracks her monthly budget**

1. **Start of month (Jan 1):**
   - Sarah opens the app
   - Enters her monthly income: $4,000
   - Sets category budgets:
     - Rent: $1,200
     - Groceries: $400
     - Dining: $200
     - Entertainment: $150
     - Transportation: $300
     - Other: $750

2. **During the month (Jan 15):**
   - Sarah logs expenses as they occur:
     - Jan 5: Rent payment, $1,200
     - Jan 8: Grocery shopping, $87.43
     - Jan 12: Dinner out, $45.67
     - Jan 14: Gas, $52.00
   - App shows:
     - Total spent: $1,385.10
     - Remaining budget: $2,614.90
     - Category breakdown with progress bars

3. **Warning example (Jan 20):**
   - Sarah tries to log a $180 dinner expense
   - App warns: "This would put you $25.67 over your Dining budget ($200)"
   - Sarah can still record it or modify the amount

4. **End of month (Jan 31):**
   - Sarah reviews spending summary
   - Sees she stayed under budget by $127.35
   - Can export data or start fresh for February
```

**Example - Poor:**
```markdown
## Example Use Case

User enters income and expenses. App shows totals.
```

**Why the first is better**: Concrete numbers, step-by-step flow, shows what user sees, includes edge case (warning scenario).

---

### 4. Inputs

**Purpose**: Specify what data users will provide.

**What to Include:**
- Each type of input
- Format or constraints (if known)
- Whether it's required or optional
- Examples with actual values

**Example - Good:**
```markdown
## Inputs

**Monthly Income:**
- Format: Dollar amount (e.g., $4,000 or 4000)
- Required: Yes
- When: Once at start of month
- Example: $4,250.00

**Expense Entry:**
- Amount: Dollar amount (e.g., $45.67)
- Category: One of (Rent, Groceries, Dining, Entertainment, Transportation, Other)
- Date: When expense occurred (defaults to today)
- Description: Optional text (e.g., "Grocery shopping at Safeway")
- Example: $87.43, Groceries, Jan 8, "Weekly shopping"

**Category Budgets (optional):**
- Category name and dollar limit
- Example: Dining: $200
```

**Example - Poor:**
```markdown
## Inputs

Users enter their money stuff.
```

**Why the first is better**: Specific data types, examples with real values, indicates what's required vs. optional.

---

### 5. Expected Outputs

**Purpose**: Show what the system should produce.

**What to Include:**
- What information is displayed
- Format of results
- Visual layout (if relevant)
- Example output with actual data

**Example - Good:**
```markdown
## Expected Outputs

**Budget Summary Display:**
```
Monthly Income: $4,000.00
Total Spent:    $1,385.10
Remaining:      $2,614.90

Category Breakdown:
- Rent:           $1,200.00 / $1,200.00 [████████████████████] 100%
- Groceries:      $   87.43 / $  400.00 [████░░░░░░░░░░░░░░░░]  22%
- Dining:         $   45.67 / $  200.00 [████░░░░░░░░░░░░░░░░]  23%
- Transportation: $   52.00 / $  300.00 [███░░░░░░░░░░░░░░░░░]  17%
- Other:          $    0.00 / $  750.00 [░░░░░░░░░░░░░░░░░░░░]   0%
```

**Warning Messages:**
- "Warning: This expense would put you $25.67 over your Dining budget"
- "Alert: You've used 90% of your Entertainment budget"

**Export Format (optional):**
- CSV file with columns: Date, Category, Amount, Description
```

**Example - Poor:**
```markdown
## Expected Outputs

Show the user their budget information.
```

**Why the first is better**: Shows exact format, includes example data, specifies different output types.

---

### 6. Important Considerations

**Purpose**: Communicate constraints, preferences, and special requirements.

**What to Include:**
- Technical constraints (if any)
- Quality requirements (performance, accuracy, etc.)
- Domain standards or compliance needs
- User experience preferences
- Known edge cases or concerns

**Example - Good:**
```markdown
## Important Considerations

**Technical Constraints:**
- Must work in a web browser (Chrome, Firefox, Safari)
- No backend server required (can run entirely in browser)
- Data should persist between sessions (localStorage is fine)

**Data Handling:**
- All currency calculations must use 2 decimal places
- Round to nearest cent for display
- Allow negative "income" for months where expenses exceed income

**User Experience:**
- Should be usable on mobile phones (responsive design)
- Simple interface - no complicated menus or options
- Fast - updates should be instant (no loading spinners)

**Edge Cases:**
- What if user enters negative expense? (Allow, treat as refund)
- What if user changes income mid-month? (Allow, recalculate remaining)
- What if total category budgets don't equal income? (That's okay, just warn)

**Not Critical:**
- Multi-currency support (USD only is fine)
- Historical analysis (just current month)
- Sharing budgets with others
```

**Example - Poor:**
```markdown
## Important Considerations

Make it work well.
```

**Why the first is better**: Specific constraints, addresses edge cases, clarifies priorities, mentions what's NOT critical.

---

## Tips for Different Project Types

### Financial / Calculation Projects

**Emphasize:**
- Specific formulas or calculation methods
- Precision requirements (decimal places, rounding)
- Valid ranges for inputs
- Edge cases (zero, negative, very large numbers)
- Expected calculation outputs with examples

**Example:**
```markdown
## Calculation Method

Use compound interest formula:
A = P(1 + r/n)^(nt)

Where:
- P = Principal ($10,000)
- r = Annual rate (0.065 for 6.5%)
- n = Compounding frequency (12 for monthly)
- t = Time in years (5)

Expected result: $13,863.29
```

---

### Game / Interactive Projects

**Emphasize:**
- Core game mechanics (how it works)
- Win/lose conditions
- Player controls and inputs
- Game loop / turn structure
- Difficulty or progression

**Example:**
```markdown
## Core Mechanics

Snake game where:
- Snake moves continuously in current direction
- Arrow keys change direction (can't reverse directly)
- Eating food makes snake longer
- Game ends if snake hits wall or itself
- Score = number of food items eaten

Win condition: Score of 20
Lose condition: Snake collision
```

---

### Web / API Projects

**Emphasize:**
- Authentication requirements
- API endpoints and their purposes
- Data persistence needs
- User roles or permissions
- Performance requirements

**Example:**
```markdown
## API Requirements

**Endpoints needed:**
- POST /api/expenses - Add new expense
- GET /api/expenses - List all expenses for month
- GET /api/summary - Get budget summary

**Authentication:**
- No login required for MVP
- Data scoped to browser session

**Data Storage:**
- Must persist between page refreshes
- Can use browser localStorage (no database needed)
```

---

### Data Processing / CLI Projects

**Emphasize:**
- Input data format and examples
- Output data format and examples
- Data validation rules
- Error handling for invalid data
- Performance with large datasets

**Example:**
```markdown
## Input Data Format

CSV file with columns:
Date,Category,Amount,Description
2025-01-05,Rent,1200.00,Monthly rent
2025-01-08,Groceries,87.43,Safeway shopping

**Validation:**
- Date must be valid YYYY-MM-DD
- Category must be one of allowed values
- Amount must be positive number with max 2 decimal places
- Description is optional

**Invalid row handling:**
- Skip row and log error
- Continue processing remaining rows
- Report count of skipped rows at end
```

---

## Common Mistakes to Avoid

### 1. Being Too Vague

❌ **Poor**: "I need a calculator that works well."

✅ **Good**: "I need a loan payment calculator that shows monthly payment, total interest, and amortization schedule for a given principal, rate, and term."

---

### 2. Specifying Implementation Details

❌ **Poor**: "Use React with Redux for state management, PostgreSQL database, REST API with JWT authentication."

✅ **Good**: "Need user authentication, data should persist between sessions, and multiple users should have separate data."

**Why**: Let the AI models choose the best implementation approach. Focus on WHAT, not HOW.

---

### 3. Assuming Domain Knowledge

❌ **Poor**: "Calculate APR using Regulation Z method."

✅ **Good**: "Calculate Annual Percentage Rate (APR) for loan comparison. Should match the APR shown on official loan documents. Example: $10,000 loan at 6% with $50 origination fee should show APR of 6.5%."

**Why**: Don't assume AI knows your domain's specific methods or standards.

---

### 4. Missing Examples

❌ **Poor**: "Calculate interest on a loan."

✅ **Good**:
```markdown
Calculate interest on a loan.

Example:
- Loan: $10,000
- Rate: 6% annual
- Term: 5 years
- Expected monthly payment: $193.33
- Expected total interest: $1,599.68
```

**Why**: Examples make requirements concrete and testable.

---

### 5. Forgetting Edge Cases

❌ **Poor**: "Divide principal by number of payments."

✅ **Good**:
```markdown
Divide principal by number of payments.

Edge cases:
- If payments = 0, show error "Number of payments must be greater than 0"
- If principal is negative, show error "Principal must be positive"
- If principal is very large (>1 million), warn "Results may be approximate"
```

**Why**: Edge cases affect user experience and prevent errors.

---

## How Much Detail is Enough?

### Too Little (will trigger clarification requests):
```markdown
# User Request

I want a budget app.
```

**Problem**: No context, no examples, no specifics.

---

### Too Much (unnecessary technical detail):
```markdown
# User Request

I want a budget app built with React 18.2, using TypeScript with strict mode,
Tailwind CSS for styling, Vite as the build tool, Zustand for state management,
React Router v6 for navigation, and Vitest for testing. The component structure
should use atomic design principles with atoms, molecules, and organisms...
```

**Problem**: This is implementation detail, not requirements.

---

### Just Right:
```markdown
# User Request - Budget Tracker

## Problem Statement
I lose track of monthly spending and often overspend on non-essentials.
I need visibility into where my money goes so I can make better decisions.

## What I Need
Simple budget tracking that:
- Tracks monthly income
- Records expenses by category
- Shows remaining budget
- Warns when approaching limits

## Example Use Case
1. Start of month: Enter income $4,000
2. Set budgets: Groceries $400, Dining $200, etc.
3. Log expenses as they occur
4. See real-time budget remaining
5. Get warning if expense exceeds category budget

## Inputs
- Monthly income (dollar amount)
- Expenses: amount, category, date, description
- Category budgets (optional limits per category)

## Expected Outputs
- Budget summary showing spent vs. remaining
- Category breakdown with percentages
- Warnings when overspending

## Important Considerations
- Must work in web browser
- Mobile-friendly design
- Data should persist between sessions
- No login required for MVP
- Support basic categories: Rent, Groceries, Dining, Entertainment, Other
```

**Why this works**: Clear problem, specific features, concrete examples, no implementation details.

---

## Length Guidelines

**Ideal length**: 1-3 pages (300-1000 words)

**Minimum (for simple projects)**: ½ page with problem, use case, and examples
**Maximum (for complex projects)**: 4-5 pages with extensive examples and edge cases

**Rule of thumb**: If someone unfamiliar with your project reads this, can they understand:
- What problem you're solving?
- What the software should do?
- What success looks like?

If yes, it's probably good enough.

---

## Iterative Approach: USER_RESPONSE.md

If the AI models request clarification, they'll create `CLARIFICATION_REQUEST.md`. You then create `USER_RESPONSE.md` with your answers.

**Structure for USER_RESPONSE.md:**

```markdown
# User Response - Clarification Round 1

## Response to Question 1: [Question Title]

[Your answer with specifics and examples]

---

## Response to Question 2: [Question Title]

[Your answer]

---

## Additional Context

[Any additional information that came up while answering]
```

**Tips:**
- Answer each question specifically
- Provide examples in your answers
- If you don't know the answer to a question, say so and suggest a reasonable default
- Don't just say "yes" or "no" - provide context

---

## Quick Checklist

Before submitting your USER_REQUEST.md, verify:

- [ ] Problem statement explains WHY this matters
- [ ] Features/capabilities are listed specifically
- [ ] At least one concrete example use case with real data
- [ ] Inputs are described with examples
- [ ] Expected outputs are shown (ideally with example format)
- [ ] Known constraints or requirements are mentioned
- [ ] Edge cases or special scenarios are addressed
- [ ] No implementation details (no specific libraries, frameworks, or code structure)
- [ ] Someone unfamiliar with the project could understand it
- [ ] Examples use real values, not placeholders like "xxx" or "some number"

---

## Examples of Complete USER_REQUEST.md Files

See `docs/instruction_file_examples.md` for complete examples across different domains:
- Financial Application (loan calculator)
- Game Development (Snake game)
- Web API Service (todo list API)
- Data Processing Tool (CSV expense analyzer)
- Web UI Enhancement (budget tracker with UI)

---

## Summary

**The Golden Rule**: Write your USER_REQUEST.md as if you're explaining the project to a smart colleague who knows nothing about your domain. Be specific, provide examples, and focus on WHAT you need, not HOW to build it.

**Remember**:
- ✅ Specific problem statements
- ✅ Concrete examples with real data
- ✅ Clear inputs and outputs
- ✅ Known edge cases and constraints
- ❌ No implementation details
- ❌ No vague language
- ❌ No assumptions about domain knowledge

**When in doubt**: Add another example. Examples clarify requirements better than descriptions.

---

## Getting Help

If you're unsure whether your USER_REQUEST.md is good enough:
1. Run it through the PRD creation phase
2. If you get CLARIFICATION_REQUEST.md back, that's okay - answer the questions
3. Usually 1-2 rounds of clarification results in a solid PRD
4. Learn from the questions asked - they'll help you write better requests in the future

The AI models are designed to ask for clarification rather than guess, so don't worry about getting it perfect the first time. The process is iterative by design.
