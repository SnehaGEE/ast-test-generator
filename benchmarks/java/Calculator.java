// Menu-driven calculator on two integers.
import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);

        System.out.println("1. Add  2. Subtract  3. Multiply  4. Divide");
        System.out.print("Choice: ");
        int choice = in.nextInt();
        System.out.print("Two numbers: ");
        int a = in.nextInt();
        int b = in.nextInt();

        switch (choice) {
            case 1:
                System.out.println("Sum: " + (a + b));
                break;
            case 2:
                System.out.println("Difference: " + (a - b));
                break;
            case 3:
                System.out.println("Product: " + (a * b));
                break;
            case 4:
                if (b == 0) {
                    System.out.println("Cannot divide by zero");
                } else {
                    System.out.println("Quotient: " + (a / b));
                }
                break;
            default:
                System.out.println("Invalid choice");
        }
    }
}
