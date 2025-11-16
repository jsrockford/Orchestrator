# User Request: Credit Card Balance Transfer Calculator

## Background

I have credit card debt and I'm trying to decide if I should transfer it to a new card with a promotional 0% interest rate, or just keep paying it off on my current card.

## The Problem

My current credit card charges interest every month on my balance. I found a new credit card that offers 0% interest for a certain number of months, but they charge a one-time fee to transfer my balance to their card. I want to know which option will cost me less money overall.

## What I Know

I have this information available:
- How much debt I currently owe
- What interest rate my current card charges (the APR percentage)
- What percentage fee the new card charges to transfer the balance
- How many months the 0% promotional rate lasts on the new card
- How much I can afford to pay each month toward the debt

## What I Need

I need a tool that will:
1. Calculate how much I'll pay in total interest if I stay with my current card
2. Calculate how much I'll pay (including the transfer fee) if I switch to the new card
3. Tell me which option is cheaper and by how much

## Example Scenario

For example, let's say:
- I owe $5,000 on my current card
- My current card charges 18% APR (annual interest rate)
- The new card charges a 3% balance transfer fee
- The new card offers 0% interest for 12 months
- I can pay $500 per month

I want to know: Should I pay the 3% fee ($150) to transfer to the 0% card, or just keep paying off my current card at 18% interest?

## Constraints

- I have a fixed monthly budget for payments (same amount every month)
- I want accurate calculations that match how credit cards actually work
- I need to know what happens if I can't pay off the full balance during the 0% promotional period

## Output Preference

I'd like to see:
- A clear recommendation (which option is better)
- How much money I'll save by choosing the better option
- Maybe a breakdown showing how the calculations work (optional, but helpful)

## Technical Level

I'm not a programmer, so I'd prefer something simple to use - maybe a command-line tool where I just enter the numbers and get an answer, or something I can run with Python if that's easier to build.

## Questions I'm Unsure About

- What happens if the debt isn't paid off during the 0% promotional period? Does it start charging interest on the remaining balance?
- Should the tool account for compound interest or simple interest?
- Are there any other fees or factors I should consider?

## Priority

This is important to me because I want to make the best financial decision, but it doesn't need to be fancy - just accurate and reliable.
