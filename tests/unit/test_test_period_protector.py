import unittest
from unittest.mock import MagicMock, patch

# Assuming the following imports are correct based on the project structure
from src.domain.services.core.test_period_protector import TestPeriodProtector
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.models.timetable import Subject, Teacher
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment

class TestTestPeriodProtector(unittest.TestCase):

    def setUp(self):
        """Set up a mock school and schedule for testing."""
        self.school = School()
        # Mocking classes
        self.class_ref1 = ClassReference(grade=1, class_number=1)
        # This is a simplified mock. A real implementation might need more setup.
        self.school.get_all_classes = MagicMock(return_value=[self.class_ref1])

        self.schedule = Schedule()

        # Mock parser
        self.mock_parser = MagicMock()
        
        # Mock test periods data
        # Let's assume Monday 1st and 2nd periods are test periods
        self.test_periods_data = [
            MagicMock(day='月', periods=[1, 2])
        ]
        self.mock_parser.parse_test_periods.return_value = self.test_periods_data
        self.mock_parser.get_special_instructions.return_value = []

    def test_protector_locks_all_test_period_cells(self):
        """
        Verify that TestPeriodProtector correctly locks all cells (including empty ones)
        during the test periods.
        """
        # Arrange
        # Let's have one slot assigned and one empty within the test period
        teacher = Teacher(name='高橋') # Valid teacher name
        subject = Subject(name='数学') # Valid subject name, assuming '数' is normalized to '数学'
        assignment = Assignment(teacher=teacher, subject=subject, class_ref=self.class_ref1)
        
        # Monday 1st period has a class
        # We need to handle potential exceptions if assign method is strict
        try:
            self.schedule.assign(TimeSlot('月', 1), assignment)
        except Exception as e:
            self.fail(f"Setup assignment failed: {e}")

        # Act
        with patch('src.infrastructure.di_container.get_followup_parser', return_value=self.mock_parser):
            protector = TestPeriodProtector(followup_parser=self.mock_parser)
            protector.protect_test_periods(self.schedule, self.school)

        # Assert
        # Check that both Monday 1st and 2nd period cells are locked
        self.assertTrue(self.schedule.is_locked(TimeSlot('月', 1), self.class_ref1))
        self.assertTrue(self.schedule.is_locked(TimeSlot('月', 2), self.class_ref1))
        
        # Check a non-test period cell is not locked
        self.assertFalse(self.schedule.is_locked(TimeSlot('火', 1), self.class_ref1))

    def test_locked_cells_prevent_modification(self):
        """
        Verify that once a cell is locked by the protector, its content cannot be changed.
        """
        # Arrange
        with patch('src.infrastructure.di_container.get_followup_parser', return_value=self.mock_parser):
            protector = TestPeriodProtector(followup_parser=self.mock_parser)
            protector.protect_test_periods(self.schedule, self.school)

        # Act & Assert
        # Try to assign a new subject to a locked empty cell
        new_teacher = Teacher(name='鈴木')
        new_subject = Subject(name='社会') # Using another valid subject '社'
        new_assignment = Assignment(teacher=new_teacher, subject=new_subject, class_ref=self.class_ref1)
        
        # The assign method should raise an exception for locked cells.
        # We assert that this specific exception is raised.
        with self.assertRaises(Exception): # Replace with a more specific exception if available
            self.schedule.assign(TimeSlot('月', 2), new_assignment)

        # Additionally, verify the cell is still empty
        self.assertIsNone(self.schedule.get_assignment(TimeSlot('月', 2), self.class_ref1))

if __name__ == '__main__':
    unittest.main()