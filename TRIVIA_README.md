# Trivia Question Files

## Format

Trivia questions are stored in JSON format with the following structure:

```json
{
  "title": "Topic Name",
  "description": "Brief description of the question set",
  "questions": [
    {
      "id": 1,
      "question": "Question text here?",
      "choices": ["Choice 1", "Choice 2", "Choice 3", "Choice 4", "Choice 5"],
      "correct": 2
    }
  ]
}
```

## Fields

- **title**: Display name for the trivia set
- **description**: Optional description of the topic
- **questions**: Array of question objects
  - **id**: Unique identifier for the question (sequential numbering recommended)
  - **question**: The question text
  - **choices**: Array of exactly 5 answer choices
  - **correct**: Index (0-4) of the correct answer in the choices array

## Included Files

- `trivia_general_knowledge.json` - 330 comprehensive questions covering:
  - General knowledge (geography, culture, famous people, basic facts)
  - Science (biology, chemistry, physics, earth science)
  - History (world history, ancient civilizations, historical events)

## Question Randomization

Questions are automatically randomized each time the trivia task starts, ensuring:
- No two sessions have the same question order
- Participants cannot memorize question sequences
- Fresh experience for each experimental session

The randomization happens when the trivia window loads, using Python's `random.shuffle()` function on the loaded questions.

## Choice Randomization

In addition to randomizing question order, the answer choices for each question are also shuffled to prevent position bias. This ensures:
- Correct answers are evenly distributed across all 5 positions
- Participants cannot develop patterns (e.g., "when in doubt, choose C")
- More valid assessment of actual knowledge rather than test-taking strategy

The choice shuffling is tracked internally so that:
- The correct answer is properly identified regardless of position
- CSV output includes both the shuffled position and original position for analysis
- Scoring remains accurate despite the randomization

## Creating Custom Trivia Files

To create your own trivia file:

1. Create a new JSON file following the format above
2. Ensure each question has exactly 5 choices
3. Set the `correct` field to the index (0-4) of the correct answer
4. Include at least 100 questions for adequate variety
5. Save the file in the Eye-State-Detector directory
6. Select it in the Setup window's Interactive task file picker

## Usage

During the interactive task portion of the experiment:
1. If SANDE/OSDI questionnaires are enabled, they appear first
2. After questionnaires (or immediately if disabled), trivia questions begin
3. Questions are presented one at a time with 5 multiple choice options
4. Participants select their answer and proceed to the next question
5. A countdown timer bar at the bottom shows remaining time
6. Current score is displayed at the top of each question
7. Questions continue until time expires
8. Final score is displayed with percentage and total questions answered
9. Results are saved to `trivia/` subfolder with both CSV and summary files
