# BrightPath Lending - Consumer Lending Policy

This policy sets out how BrightPath Lending decides applications for personal loans and car loans. An underwriter reads the application, the credit file and the attached documents, and makes one decision: approve, decline or refer.

## 1. Products

| Product | Minimum | Maximum | Terms (months) | Extra requirement |
|---|---|---|---|---|
| Personal loan | $1,000 | $40,000 | 24, 36 or 60 | None |
| Car loan | $5,000 | $60,000 | 36 or 60 | A dealer or private-sale vehicle quote |

A car loan can never be more than the price on the vehicle quote.

## 2. Prohibited purposes

We do not lend for gambling, for buying cryptocurrency or other speculative investments, or for business use on a personal loan. An application for a prohibited purpose is declined.

## 3. Required documents

Every application needs:

- A photo ID (`id`)
- A bank statement covering the last three months (`bank_statement`)

Employees also need recent payslips (`payslip`). Self-employed applicants also need tax returns for each of the last two tax years (`tax_return`, two documents). Car loans also need a vehicle quote (`vehicle_quote`).

## 4. Verified income

We lend on verified income, never on the income the applicant states.

- Employees: the annual salary shown on the payslips.
- Self-employed: the average of the net business income on the last two tax returns.

If the stated annual income is more than 10% above the verified income, the application is referred so an underwriter can find out why.

## 5. Hard declines

Decline the application if any of these is true:

- The applicant is under 18.
- The credit score is below 580.
- The applicant had a bankruptcy discharged in the 24 months before the application date.
- The credit file shows 3 or more missed payments in the last 12 months.
- The applicant is self-employed and has been trading for less than 24 months.
- The purpose is prohibited (section 2).

## 6. Referrals

Refer the application to a senior underwriter if any of these is true, and no hard decline applies:

- A required document is missing (section 3).
- The stated income is more than 10% above the verified income (section 4).
- The credit score is 580 to 619.
- The applicant is a temporary resident. Citizens and permanent residents can be decided as normal.
- The applicant is an employee who has been in their current job for less than 6 months.
- The story, the application or the documents disagree with each other, for example a debt in the bank statement that the application does not declare.

## 7. Income limit

The loan can be no more than a multiple of the verified annual income, set by the credit score:

| Credit score | Maximum loan as a share of verified annual income |
|---|---|
| 620 to 679 | 25% |
| 680 to 739 | 40% |
| 740 and above | 50% |

## 8. Affordability

The estimated monthly payment on a loan is the loan amount multiplied by the payment factor for its term:

| Term | Payment factor |
|---|---|
| 24 months | 0.047 |
| 36 months | 0.033 |
| 60 months | 0.022 |

The debt-to-income ratio (DTI) is the existing monthly debt payments plus the estimated new payment, divided by the verified monthly income (verified annual income / 12).

The DTI may be no more than 40%, or 45% when the credit score is 740 or above.

## 9. Working out the approved amount

1. Start with the amount requested.
2. Reduce it to the product maximum (section 1), the vehicle price for a car loan, and the income limit (section 7), whichever is lowest.
3. Check the DTI at that amount (section 8). If it is over the limit, reduce the amount to the largest amount that keeps the DTI at or under the limit.
4. If the amount was reduced in step 2 or step 3, round it down to the nearest $500.
5. If the result is below the product minimum, decline. Otherwise approve that amount.

The approved amount is 0 for a decline or a referral.

## 10. Order of decisions

Check the hard declines (section 5) first, then the referrals (section 6), then work out the approved amount (section 9).
